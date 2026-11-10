"""Small, cached, user-triggered catalog searches. Provider credentials stay on server."""
import json
import os
import re
import time
import urllib.request
import urllib.parse
from threading import Lock
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

class CatalogInfo(BaseModel):
    source: Literal['Open Library', 'Google Books', 'Shikimori', 'TMDB']
    external_id: str = Field(max_length=100)
    title: str = Field(max_length=300)
    image: str | None = Field(default=None, max_length=2000)
    poster_source: Literal['TMDB'] | None = None
    author: str = Field(default='', max_length=500)
    year: str = Field(default='', max_length=50)
    description_source: Literal['Open Library', 'Google Books'] | None = None
    description: str = Field(default='', max_length=10000)
    genres: list[str] = Field(default_factory=list, max_length=30)
    isbn: str = Field(default='', max_length=20)
    publisher: str = Field(default='', max_length=500)
    pages: int | None = Field(default=None, gt=0)
    episodes: int | None = Field(default=None, gt=0)
    seasons: int | None = Field(default=None, gt=0)
    runtime: int | None = Field(default=None, gt=0)
    score: float | None = Field(default=None, ge=0, le=10)
    studio: str = Field(default='', max_length=500)
    original_title: str = Field(default='', max_length=300)

_cache = {}
_lock = Lock()
_last = {}

def _get(url, headers=None):
    # Serialize public requests, respect public catalog limits; cache for an hour.
    with _lock:
        cached = _cache.get(url)
        if cached and time.monotonic() - cached[0] < 3600:
            return cached[1]
        host = urllib.parse.urlparse(url).hostname
        pause = 1.05 - (time.monotonic() - _last.get(host, 0))
        if pause > 0:
            time.sleep(pause)
        _last[host] = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'FitPulse/1.0 (https://github.com/R1ch1131/fitness-bot)', **(headers or {})})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except Exception:
            raise HTTPException(502, 'Каталог временно недоступен. Попробуй позже или добавь вручную.') from None
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        _cache[url] = (time.monotonic(), data)
        return data

def _positive(value):
    return value if isinstance(value, int) and value > 0 else None

def search_catalog(kind, title, author=''):
    title = title.strip()
    if not 2 <= len(title) <= 200:
        raise HTTPException(422, 'Введи название от 2 до 200 символов.')
    results = []
    if kind == 'book':
        from book_catalog import find_books
        results = find_books(title, author, _get)
    elif kind in ('movie', 'series', 'anime'):
        token = os.getenv('TMDB_READ_TOKEN', '').strip()
        if not token:
            raise HTTPException(503, 'Поиск TMDB ещё не подключён. Добавь TMDB_READ_TOKEN в настройки сервера и перезапусти приложение. Пока можно добавить название и свою обложку вручную.')
        category = 'multi' if kind == 'anime' else ('movie' if kind == 'movie' else 'tv')
        data = _get('https://api.themoviedb.org/3/search/' + category + '?' + urllib.parse.urlencode({'query': title, 'language': 'ru-RU', 'include_adult': 'false'}), {'Authorization': 'Bearer ' + token})
        candidates = data.get('results', [])
        if kind == 'anime':
            candidates = [item for item in candidates if item.get('media_type') in ('tv', 'movie') and 16 in item.get('genre_ids', [])]
        for item in candidates[:8]:
            results.append(dict(source='TMDB', external_id=f"tmdb:{item['media_type']}:{item['id']}" if kind == 'anime' else str(item['id']), title=item.get('title') or item.get('name'), original_title=item.get('original_title') or item.get('original_name') or '', image='https://image.tmdb.org/t/p/w500' + item['poster_path'] if item.get('poster_path') else None, year=(item.get('release_date') or item.get('first_air_date') or '')[:4], description=item.get('overview') or '', score=item.get('vote_average') if item.get('vote_count') else None))
    else:
        raise HTTPException(422, 'Неизвестная категория')
    return {'results': [CatalogInfo(**item).model_dump() for item in results]}

def _title_key(value):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def anime_posters(item):
    """Use the authoritative anime title, date and format, never a client URL."""
    token = os.getenv('TMDB_READ_TOKEN', '').strip()
    if not token:
        return {'poster_state': 'no_key', 'poster_options': []}
    category = 'movie' if item.get('kind') == 'movie' else 'tv'
    titles = [item.get('russian'), item.get('name'), *(item.get('english') or []), *(item.get('japanese') or [])]
    titles = [title for title in titles if title]
    year = (item.get('aired_on') or '')[:4]
    options = {}
    try:
        # Russian name catches localized titles; English/romaji handles missing translations.
        for title in list(dict.fromkeys(titles))[:3]:
            query = urllib.parse.urlencode({'query': title, 'language': 'ru-RU', 'include_adult': 'false'})
            payload = _get(f'https://api.themoviedb.org/3/search/{category}?' + query, {'Authorization': 'Bearer ' + token})
            for result in payload.get('results', [])[:20]:
                path = result.get('poster_path')
                # Do not offer live-action adaptations. An uncertain animation match is manual only.
                if not path or 16 not in result.get('genre_ids', []) or not re.fullmatch(r'/[A-Za-z0-9_.-]+', path):
                    continue
                name = result.get('title') or result.get('name') or ''
                original = result.get('original_title') or result.get('original_name') or ''
                date = (result.get('release_date') or result.get('first_air_date') or '')[:4]
                exact_title = bool({_title_key(t) for t in titles} & {_title_key(name), _title_key(original)})
                options[result['id']] = {'id': result['id'], 'title': name, 'year': date, 'image': 'https://image.tmdb.org/t/p/w500' + path, 'exact': bool(exact_title and year and date == year), 'url': f"https://www.themoviedb.org/{category}/{result['id']}"}
    except HTTPException:
        return {'poster_state': 'unavailable', 'poster_options': []}
    choices = sorted(options.values(), key=lambda result: not result['exact'])[:8]
    exact = [result for result in options.values() if result['exact']]
    if len(exact) == 1:
        return {'poster_state': 'matched', 'image': exact[0]['image'], 'poster_source': 'TMDB', 'poster_options': choices}
    return {'poster_state': 'choose' if choices else 'not_found', 'poster_options': choices}


def catalog_details(kind, external_id):
    if kind == 'book' and external_id.startswith('google:'):
        from book_catalog import google_details, supplement_description
        return supplement_description(google_details(external_id, _get), _get)
    if kind == 'book' and re.fullmatch(r'/works/OL\d+W', external_id):
        from book_catalog import open_library_description
        return {'description': open_library_description(external_id, _get), 'description_source': 'Open Library'}
    if kind == 'book' and re.fullmatch(r'/books/OL\d+M', external_id):
        item = _get('https://openlibrary.org' + external_id + '.json')
        description = item.get('description', '')
        if isinstance(description, dict):
            description = description.get('value', '')
        if not description:
            from book_catalog import open_library_description
            description = open_library_description(external_id, _get)
        return {'pages': _positive(item.get('number_of_pages')), 'publisher': ', '.join(item.get('publishers', []))[:500], 'year': str(item.get('publish_date') or '')[:50], 'description': str(description)[:10000], **({'image': f"https://covers.openlibrary.org/b/id/{item['covers'][0]}-L.jpg"} if item.get('covers') and item['covers'][0] > 0 else {})}
    match = re.fullmatch(r'tmdb:(tv|movie):(\d+)(?::season:(\d+))?', external_id) if kind == 'anime' else None
    if match:
        category, identifier, season = match.groups()
        if season is not None and category != 'tv':
            return {}
        token = os.getenv('TMDB_READ_TOKEN', '').strip()
        if not token:
            raise HTTPException(503, 'Добавь TMDB_READ_TOKEN в настройки сервера.')
        path = f'{category}/{identifier}' + (f'/season/{season}' if season is not None else '')
        item = _get(f'https://api.themoviedb.org/3/{path}?language=ru-RU', {'Authorization': 'Bearer ' + token})
        result = {'genres': [g['name'] for g in item.get('genres', [])], 'runtime': _positive(item.get('runtime')), 'description': (item.get('overview') or '')[:10000], 'episodes': (_positive(len(item.get('episodes', []))) if season is not None else (1 if category == 'movie' else _positive(item.get('number_of_episodes'))))}
        if item.get('poster_path'):
            result['image'] = 'https://image.tmdb.org/t/p/w500' + item['poster_path']
        if category == 'tv' and season is None:
            name = item.get('name') or ''
            result['season_options'] = [CatalogInfo(source='TMDB', external_id=f"tmdb:tv:{identifier}:season:{entry['season_number']}", title=(name + ' — ' + (entry.get('name') or f"Сезон {entry['season_number']}"))[:200], image='https://image.tmdb.org/t/p/w500' + (entry.get('poster_path') or item.get('poster_path')) if entry.get('poster_path') or item.get('poster_path') else None, episodes=_positive(entry.get('episode_count')), year=(entry.get('air_date') or '')[:4], description=(entry.get('overview') or item.get('overview') or '')[:10000], genres=result['genres']).model_dump() for entry in item.get('seasons', []) if isinstance(entry.get('season_number'), int) and entry['season_number'] >= 0]
        return result
    if kind == 'anime' and external_id.isdigit():
        item = _get('https://shikimori.one/api/animes/' + external_id)
        description = re.sub(r'\[/?[^\]]+\]', '', item.get('description') or '')
        result = {'description': description[:10000], 'genres': [g.get('russian') or g['name'] for g in item.get('genres', [])], 'studio': ', '.join(g['name'] for g in item.get('studios', []))[:500], 'runtime': _positive(item.get('duration')), 'episodes': _positive(item.get('episodes'))}
        path = item.get('image', {}).get('original') or ''
        if not path.startswith('/system/'):
            result.update(anime_posters(item))
        return result
    if kind in ('movie', 'series') and external_id.isdigit():
        token = os.getenv('TMDB_READ_TOKEN', '').strip()
        if not token:
            raise HTTPException(503, 'Добавь TMDB_READ_TOKEN в настройки сервера.')
        category = 'movie' if kind == 'movie' else 'tv'
        item = _get(f'https://api.themoviedb.org/3/{category}/{external_id}?language=ru-RU', {'Authorization': 'Bearer ' + token})
        return {'genres': [g['name'] for g in item.get('genres', [])], 'runtime': _positive(item.get('runtime')), 'episodes': _positive(item.get('number_of_episodes')), 'seasons': _positive(item.get('number_of_seasons'))}
    return {}

router = APIRouter(prefix='/api/catalog')
@router.get('/search')
def search(kind: Literal['book', 'movie', 'series', 'anime'], title: str = Query(min_length=2, max_length=200), author: str = Query(default='', max_length=500)):
    return search_catalog(kind, title, author)
@router.get('/details')
def details(kind: Literal['book', 'movie', 'series', 'anime'], external_id: str = Query(max_length=100)):
    return catalog_details(kind, external_id)

@router.get('/anime-posters')
def find_anime_posters(external_id: str = Query(pattern=r'^\d+$', max_length=20)):
    item = _get('https://shikimori.one/api/animes/' + external_id)
    return anime_posters(item)
