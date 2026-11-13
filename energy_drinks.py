"""Personal energy drink ratings, stored independently of the media collection."""
import json
import os
import ipaddress
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from threading import RLock, Lock
from urllib.parse import urlencode, urlsplit
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from cloud_storage import get_cloud_data, set_cloud_data, is_cloud_configured, CloudStorageError
from config import DATA_DIR
from media_covers import normalize_cover
from catalog import _get


PRODUCT_IMAGE_HOSTS = {'images.openfoodfacts.org', 'c1.neweggimages.com', 'i5.walmartimages.com', 'pics.walgreens.com', 'products.blains.com', 'scene7.samsclub.com', 'target.scene7.com', 'tshop.r10s.com', 'www.cvs.com', 'i28.onbuy.com', 'www0.alibris-static.com', 'm.media-amazon.com', 'images-na.ssl-images-amazon.com'}


def product_image(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        return value if url.scheme == 'https' and url.hostname in PRODUCT_IMAGE_HOSTS and not url.username and not url.password and url.port in (None,443) else None
    except ValueError:
        return None


def web_image(value):
    """Public HTTPS URLs displayed by the browser; never fetched by our server."""
    if not isinstance(value, str) or len(value) > 8000:
        return None
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower().rstrip('.')
        if url.scheme != 'https' or not host or '.' not in host or url.username or url.password or url.port not in (None, 443):
            return None
        if host.endswith(('.localhost', '.local', '.internal', '.test')) or host == 'localhost':
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value
    except ValueError:
        return None


class DrinkInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=10)
    image_source: Literal['UPCitemdb', 'Open Food Facts', 'Serper'] | None = None
    image_page: str | None = Field(default=None, max_length=8000)
    notes: str = Field(default='', max_length=10000)
    image: str | None = Field(default=None, max_length=3_000_000)
    @model_validator(mode='after')
    def clean(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Укажи название энергетика')
        self.image = (web_image(self.image) if self.image_source == 'Serper' else product_image(self.image)) or normalize_cover(self.image)
        self.image_page = web_image(self.image_page)
        return self


class DrinkStore:
    def __init__(self, path=DATA_DIR / 'energy_drinks.json'):
        self.path = Path(path)
        self.lock = RLock()
    def read(self):
        try:
            data = get_cloud_data('athlete_energy_drinks', strict=True) if is_cloud_configured() else json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
        except (CloudStorageError, OSError, ValueError):
            raise HTTPException(503, 'Не удалось прочитать коллекцию энергетиков. Попробуй позже.') from None
        data = [] if data is None else data
        if not isinstance(data,list) or any(not isinstance(item,dict) or not item.get('id') or not item.get('title') for item in data):
            raise HTTPException(503, 'Не удалось прочитать коллекцию. Изменения заблокированы.')
        return data
    def write(self, items):
        if is_cloud_configured():
            if not set_cloud_data('athlete_energy_drinks',items):
                raise HTTPException(503, 'Облако не подтвердило сохранение. Повтори попытку.')
        else:
            try:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                temporary=self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
                temporary.replace(self.path)
            except OSError:
                raise HTTPException(503,'Не удалось сохранить коллекцию.') from None
    def save(self,value,item_id=None):
        with self.lock:
            items=self.read()
            if item_id is not None and not any(item['id']==item_id for item in items):
                raise HTTPException(404,'Энергетик не найден')
            item={**value.model_dump(),'id':item_id or str(uuid4())}
            items=[item if old['id']==item_id else old for old in items] if item_id else [*items,item]
            self.write(items)
            return {'items':items}
    def delete(self,item_id):
        with self.lock:
            items=self.read()
            if not any(item['id']==item_id for item in items):
                raise HTTPException(404,'Энергетик не найден')
            items=[item for item in items if item['id']!=item_id]
            self.write(items)
            return {'items':items}

_upc_lock=Lock()
_last_upc_search=0
_upc_last_state='idle'


def _upc_get(url):
    request=urllib.request.Request(url,headers={'User-Agent':'FitPulse/1.0 (https://github.com/R1ch1131/fitness-bot)', 'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return {'code':'QUOTA' if error.code==429 else 'HTTP_ERROR'}
    except (OSError,ValueError):
        return {'code':'UNAVAILABLE'}



def search_upc(title):
    """A general retail catalog. Free quota exhaustion falls back to Open Food Facts."""
    global _last_upc_search, _upc_last_state
    with _upc_lock:
        if time.monotonic()-_last_upc_search < 16:
            _upc_last_state='cooldown'
            return []
        _last_upc_search=time.monotonic()
        try:
            data=_upc_get('https://api.upcitemdb.com/prod/trial/search?'+urlencode({'s':title,'type':'product'}))
        except HTTPException:
            _upc_last_state='unavailable'
            return []
    if data.get('code') != 'OK':
        _upc_last_state='quota' if data.get('code') in ('QUOTA','TOO_MANY_REQUESTS','EXCEED_LIMIT') else 'unavailable'
        return []
    _upc_last_state='ok'
    results=[]
    images=set()
    for item in data.get('items',[]):
        for index, value in enumerate((item.get('images') or [])[:2]):
            image=product_image(value)
            if image and image not in images and item.get('title'):
                images.add(image)
                results.append({'id':'upc:'+str(item.get('ean') or item.get('upc') or len(results))+':'+str(index), 'title':str(item['title'])[:200], 'brand':str(item.get('brand') or '')[:200], 'quantity':'', 'image':image, 'source':'UPCitemdb'})
    return results[:8]


_search_lock=Lock()
_search_cache={}
_last_search=0

SERPER_CACHE_FILE = DATA_DIR / 'energy_image_search_cache.json'
SERPER_CACHE_KEY = 'athlete_energy_image_search_cache'
SERPER_CACHE_TTL = 30 * 86400


def _read_image_cache():
    try:
        data = get_cloud_data(SERPER_CACHE_KEY, strict=True) if is_cloud_configured() else json.loads(SERPER_CACHE_FILE.read_text(encoding='utf-8')) if SERPER_CACHE_FILE.exists() else {}
    except (CloudStorageError, OSError, ValueError):
        # A failed cache read must not silently spend another paid search.
        raise HTTPException(503, 'Не удалось прочитать кеш картинок. Повтори поиск позже.') from None
    if data is not None and not isinstance(data, dict):
        raise HTTPException(503, 'Кеш картинок временно недоступен.')
    return {key: value for key, value in (data or {}).items() if isinstance(value, dict) and isinstance(value.get('at'), (int, float)) and time.time() - value['at'] < SERPER_CACHE_TTL and isinstance(value.get('results'), list)}


def _write_image_cache(data):
    data = dict(sorted(data.items(), key=lambda item: item[1]['at'])[-128:])
    if is_cloud_configured():
        return set_cloud_data(SERPER_CACHE_KEY, data)
    try:
        SERPER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = SERPER_CACHE_FILE.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temporary.replace(SERPER_CACHE_FILE)
        return True
    except OSError:
        return False


def _serper_request(title, key):
    request = urllib.request.Request('https://google.serper.dev/images',
        data=json.dumps({'q': title + ' energy drink can product', 'num': 10, 'hl': 'ru'}).encode('utf-8'),
        headers={'X-API-KEY': key, 'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get('images'), list):
            raise ValueError()
        return data
    except urllib.error.HTTPError as error:
        message = 'Лимит Serper исчерпан или поиск временно ограничен.' if error.code in (402, 429) else 'Проверь ключ Serper в настройках сервера.' if error.code in (401, 403) else 'Serper временно недоступен.'
        raise HTTPException(503, message + ' Можно загрузить свою картинку.') from None
    except (OSError, ValueError):
        raise HTTPException(502, 'Поиск Serper временно недоступен. Можно загрузить свою картинку.') from None


def search_serper(title, key):
    cache = _read_image_cache()
    cache_key = ' '.join(title.casefold().split())
    if cache_key in cache:
        return {'results': cache[cache_key]['results'], 'provider': 'Serper', 'cached': True}
    data = _serper_request(title, key)
    results, seen = [], set()
    for item in data['images']:
        if not isinstance(item, dict):
            continue
        image = web_image(item.get('imageUrl'))
        if not image or image in seen:
            continue
        seen.add(image)
        results.append({'id': 'serper:' + str(len(results)), 'title': str(item.get('title') or title)[:200],
            'brand': str(item.get('source') or item.get('domain') or '')[:200], 'quantity': '',
            'image': image, 'image_page': web_image(item.get('link')), 'source': 'Serper'})
    # Prefer known manufacturers, retaining other brands and stores in the results.
    official = ('monsterenergy.com', 'adrenalinerush.ru', 'redbull.com', 'burn.com', 'rockstarenergy.com')
    results.sort(key=lambda item: not any((urlsplit(item.get('image_page') or '').hostname or '') == domain or (urlsplit(item.get('image_page') or '').hostname or '').endswith('.' + domain) for domain in official))
    result = {'results': results[:10], 'provider': 'Serper', 'cached': False}
    cache[cache_key] = {'at': time.time(), 'results': result['results']}
    result['cache_saved'] = _write_image_cache(cache)
    return result

def search_products(title):
    global _last_search
    title=' '.join(title.split())
    if not 2 <= len(title) <= 200:
        raise HTTPException(422,'Введи хотя бы 2 символа названия.')
    with _search_lock:
        serper_key=os.getenv('SERPER_API_KEY', '').strip()
        cache_key=('serper:' if serper_key else 'catalog:') + title.casefold()
        cached=_search_cache.get(cache_key)
        if cached and time.monotonic()-cached[0] < (SERPER_CACHE_TTL if serper_key else 3600):
            return {**cached[1], 'cached': True} if serper_key else cached[1]
        if time.monotonic()-_last_search < 6:
            raise HTTPException(429,'Подожди несколько секунд перед следующим поиском.')
        _last_search=time.monotonic()
        if serper_key:
            result=search_serper(title, serper_key)
            if len(_search_cache)>=128:
                _search_cache.pop(next(iter(_search_cache)))
            _search_cache[cache_key]=(time.monotonic(),result)
            return result
        retail_results=search_upc(title)
        if retail_results:
            result={'results':retail_results,'retail_state':_upc_last_state}
            if len(_search_cache)>=64:
                _search_cache.pop(next(iter(_search_cache)))
            _search_cache[cache_key]=(time.monotonic(),result)
            return result
        query=urlencode({'search_terms':title,'search_simple':1,'action':'process','json':1,'page_size':12,'fields':'code,product_name,product_name_ru,brands,quantity,image_front_url'})
        search_query=urlencode({'q':title,'page_size':12,'fields':'code,product_name,product_name_ru,brands,quantity,image_front_url'})
        try:
            data=_get('https://search.openfoodfacts.org/search?'+search_query)
            if data.get('errors'):
                raise HTTPException(502,'Search unavailable')
        except HTTPException:
            try:
                data=_get('https://world.openfoodfacts.org/cgi/search.pl?'+query)
            except HTTPException:
                raise HTTPException(502,'Каталог продуктов временно недоступен. Можно загрузить свою картинку.') from None
        results=[]
        for item in data.get('hits', data.get('products', [])):
            name=item.get('product_name_ru') or item.get('product_name')
            image=product_image(item.get('image_front_url'))
            if name and image:
                results.append({'id':str(item.get('code') or len(results)), 'title':str(name)[:200],'brand':(', '.join(str(brand) for brand in item['brands']) if isinstance(item.get('brands'),list) else str(item.get('brands') or ''))[:200],'quantity':str(item.get('quantity') or '')[:80],'image':image,'source':'Open Food Facts'})
        result={'results':results[:8],'retail_state':_upc_last_state}
        if len(_search_cache)>=64:
            _search_cache.pop(next(iter(_search_cache)))
        _search_cache[cache_key]=(time.monotonic(),result)
        return result

store=DrinkStore()
router=APIRouter(prefix='/api/energy-drinks')
@router.get('')
def list_drinks():
    with store.lock:
        return {'items':store.read()}
@router.get('/search')
def find_drinks(title: str=Query(min_length=2,max_length=200)):
    return search_products(title)
@router.post('')
def create_drink(value: DrinkInput):
    return store.save(value)
@router.put('/{item_id}')
def update_drink(item_id: str,value: DrinkInput):
    return store.save(value,item_id)
@router.delete('/{item_id}')
def delete_drink(item_id: str):
    return store.delete(item_id)
