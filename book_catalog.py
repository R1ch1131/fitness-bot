"""Book metadata from Google Books and edition-aware Open Library searches."""
import html
import os
import re
import urllib.parse
from fastapi import HTTPException

GOOGLE_IMAGE_HOSTS = {'books.google.com', 'books.googleusercontent.com'}
TRANSLITERATION = dict(zip('абвгдеёзийклмнопрстуфхцъыьэ', ['a','b','v','g','d','e','e','z','i','i','k','l','m','n','o','p','r','s','t','u','f','kh','ts','','y','','e']))
TRANSLITERATION.update({'ж':'zh','ч':'ch','ш':'sh','щ':'shch','ю':'iu','я':'ia'})


def romanize(value):
    return ''.join(TRANSLITERATION.get(char, char) for char in value.casefold())


def google_image(value):
    if not value:
        return None
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http','https') or parsed.netloc not in GOOGLE_IMAGE_HOSTS:
        return None
    # Do not embed credentials even if a provider adds them to a thumbnail URL.
    query=urllib.parse.urlencode([(key,val) for key,val in urllib.parse.parse_qsl(parsed.query) if key.lower() not in ('key','access_token')])
    return urllib.parse.urlunsplit(('https',parsed.netloc,parsed.path,query,''))


def _positive(value):
    return value if type(value) is int and value>0 else None


def google_volume(item):
    info=item.get('volumeInfo',{})
    identifier=str(item.get('id',''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identifier) or not info.get('title'):
        return None
    title=info['title']
    if info.get('subtitle') and info['subtitle'].casefold() not in title.casefold():
        title += ': '+info['subtitle']
    images=info.get('imageLinks') or {}
    isbn=next((str(entry.get('identifier','')) for entry in info.get('industryIdentifiers',[]) if entry.get('type')=='ISBN_13'), '')
    return {'source':'Google Books','external_id':'google:'+identifier,'title':title[:300],
            'author':', '.join(info.get('authors',[]))[:500], 'image':google_image(images.get('thumbnail') or images.get('smallThumbnail')),
            'year':str(info.get('publishedDate') or '')[:50], 'publisher':str(info.get('publisher') or '')[:500],
            'pages':_positive(info.get('pageCount')), 'description':html.unescape(re.sub(r'<[^>]*>', ' ',info.get('description') or ''))[:10000],
            'genres':info.get('categories',[])[:30], 'isbn':isbn[:20]}


def _google_get(path, params, get_json):
    key=os.getenv('GOOGLE_BOOKS_API_KEY','').strip()
    if not key:
        raise HTTPException(503,'Google Books ещё не подключён. Добавь GOOGLE_BOOKS_API_KEY в настройки сервера.')
    # Requests and API keys are confined to the server; _get hides provider URLs on failure.
    query=urllib.parse.urlencode({**params,'key':key})
    return get_json('https://www.googleapis.com/books/v1/'+path+'?'+query)


def google_details(external_id, get_json):
    identifier=external_id.removeprefix('google:')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identifier):
        raise HTTPException(422,'Некорректный идентификатор Google Books')
    data=_google_get('volumes/'+identifier,{},get_json)
    result=google_volume(data)
    if not result:
        raise HTTPException(502,'Не удалось прочитать сведения Google Books')
    return result


def _ol_results(data):
    results=[]
    for work in data.get('docs',[]):
        edition=(work.get('editions',{}).get('docs') or [{}])[0]
        title=edition.get('title') or work.get('title')
        identifier=edition.get('key') or work.get('key')
        if not title or not identifier:
            continue
        # A work's default image may belong to a different edition or language.
        cover=edition.get('cover_i') or work.get('cover_i')
        results.append({'source':'Open Library','external_id':identifier,'title':str(title)[:300],
                        'author':', '.join(work.get('author_name',[]))[:500], 'year':str(work.get('first_publish_year') or ''),
                        'image':f'https://covers.openlibrary.org/b/id/{cover}-L.jpg?default=false' if type(cover) is int and cover>0 else None})
    return results


def find_books(title, author, get_json):
    results=[]; failures=0; successes=0
    isbn=re.sub(r'[-\s]','',title.strip())
    is_isbn=bool(re.fullmatch(r'(?:\d{13}|\d{9}[\dXx])',isbn))
    if os.getenv('GOOGLE_BOOKS_API_KEY','').strip():
        query=title.strip()
        if is_isbn:query='isbn:'+isbn
        elif author.strip():query += ' '+author.strip()
        try:
            payload=_google_get('volumes',{'q':query,'maxResults':8,'printType':'books'},get_json)
            results=[result for item in payload.get('items',[]) if (result:=google_volume(item))]
            successes+=1
        except HTTPException:failures+=1
    if len(results)>=8:
        return results[:8]
    fields='key,title,author_name,first_publish_year,cover_i,editions,editions.key,editions.title,editions.cover_i'
    queries=[{'q':'isbn:'+isbn}] if is_isbn else [{'title':title}]
    latin=romanize(title)
    if re.search('[а-яё]',title,re.I) and latin!=title.casefold():queries.append({'title':latin})
    if author.strip() and not is_isbn:
        # An author fallback is offered for manual selection; it is never auto-applied.
        first=re.split(r'\s+(?:и|and|&)\s+|,',author,flags=re.I)[0]
        words=re.findall(r'[a-z]+',romanize(first))
        if words:
            digits=re.search(r'\d+',title)
            queries.append({'author':words[-1],**({'title':digits.group()} if digits else {})})
    seen={item['external_id'] for item in results}
    for query in queries:
        if len(results)>=8:break
        try:
            data=get_json('https://openlibrary.org/search.json?'+urllib.parse.urlencode({**query,'lang':'ru','limit':8,'fields':fields}))
            successes+=1
        except HTTPException:
            failures+=1;continue
        candidates=_ol_results(data)
        for item in candidates:
            if item['external_id'] not in seen:
                seen.add(item['external_id']);results.append(item)
        # A useful title match does not need another search for alternate spellings.
        if candidates and 'title' in query and any(item.get('image') for item in candidates):break
    if not results and failures and not successes:
        raise HTTPException(502,'Каталоги книг временно недоступны. Попробуй позже или загрузи свою обложку.')
    return results[:8]
