"""Optional Steam artwork and achievements. Failures never block the library."""
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.parse import urlencode

_cache = {}
_lock = Lock()


def _fetch_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        error.close()
        raise


def _cached(key, url, ttl):
    with _lock:
        saved = _cache.get(key)
        if saved and saved[0] > time.monotonic():
            return saved[1]
    value = _fetch_json(url)
    with _lock:
        # Bound memory even for a large library.
        if len(_cache) >= 512:
            _cache.clear()
        _cache[key] = (time.monotonic() + ttl, value)
    return value


def _text(value):
    return html.unescape(re.sub('<[^>]+>', '', value or '')).strip()


def _image(value):
    # Only Steam-hosted HTTPS images are returned to the browser.
    from urllib.parse import urlparse
    parsed = urlparse(value or '')
    host = parsed.hostname or ''
    return value if parsed.scheme == 'https' and (host.endswith('.steamstatic.com') or host.endswith('.steamcommunity.com') or host.endswith('.steampowered.com') or host == 'steamcdn-a.akamaihd.net') else None


def _store(appid):
    try:
        payload = _cached(('store', appid), f'https://store.steampowered.com/api/appdetails?appids={appid}&l=russian&cc=us', 3600)
        raw = payload.get(str(appid), {})
        if not raw.get('success'):
            return None
        data = raw['data']
        return {'header_image': _image(data.get('header_image')),
                'description': _text(data.get('short_description')),
                'genres': [_text(genre.get('description')) for genre in data.get('genres', [])],
                'developers': data.get('developers', []),
                'release_date': data.get('release_date', {}).get('date'),
                'screenshots': [url for shot in data.get('screenshots', [])[:4]
                                if (url := _image(shot.get('path_full')))]}
    except Exception:
        return None


def _achievements(appid, steam_id):
    key = os.getenv('STEAM_API_KEY', '').strip()
    if not key:
        return {'state': 'no_key'}
    query = urlencode({'key': key, 'appid': appid, 'steamid': steam_id, 'l': 'russian'})
    try:
        player = _cached(('player', appid, steam_id), 'https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?' + query, 300).get('playerstats', {})
        if not player.get('success'):
            return {'state': 'unavailable'}
        schema = _cached(('schema', appid), 'https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?' + query, 3600)
        definitions = schema.get('game', {}).get('availableGameStats', {}).get('achievements', [])
        # Missing schema is not proof that a game has no achievements.
        if not definitions:
            return {'state': 'none'} if not player.get('achievements') else {'state': 'unavailable'}
        owned = {entry['apiname']: entry for entry in player.get('achievements', [])}
        if 'achievements' not in player:
            return {'state': 'unavailable'}
        entries = []
        for definition in definitions:
            name = definition['name']
            progress = owned.get(name, {})
            unlocked = progress.get('achieved') == 1
            hidden = bool(definition.get('hidden')) and not unlocked
            entries.append({'id': name, 'name': 'Скрытое достижение' if hidden else _text(definition.get('displayName', name)),
                            'description': '' if hidden else _text(definition.get('description')),
                            'icon': _image(definition.get('icon' if unlocked else 'icongray')),
                            'unlocked': unlocked, 'unlocked_at': progress.get('unlocktime', 0) if unlocked else 0})
        entries.sort(key=lambda entry: (not entry['unlocked'], -entry['unlocked_at']))
        return {'state': 'ready', 'total': len(entries), 'unlocked': sum(entry['unlocked'] for entry in entries), 'entries': entries}
    except Exception:
        # Never expose upstream URLs containing a private API key.
        return {'state': 'unavailable'}


def get_game_details(appid, steam_id):
    with ThreadPoolExecutor(max_workers=2) as pool:
        store = pool.submit(_store, appid)
        achievements = pool.submit(_achievements, appid, steam_id)
        return {'store': store.result(), 'achievements': achievements.result()}
