"""Compact custom covers and public catalog artwork for manual entries."""
import base64
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from PIL import Image, ImageOps
from steam_details import _image, _store


def normalize_cover(value):
    if not value:
        return None
    if value.startswith('https://'):
        host = urllib.parse.urlparse(value).hostname
        if not _image(value) and host not in ('covers.openlibrary.org', 'cdn.myanimelist.net', 'image.tmdb.org', 'shikimori.one'):
            raise ValueError('Выбери обложку из поиска или загрузи картинку')
        return value
    try:
        prefix, encoded = value.split(',', 1)
        if prefix not in ('data:image/webp;base64', 'data:image/jpeg;base64', 'data:image/png;base64'):
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 2_000_000:
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 20_000_000 or source.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError()
            # Already-normalized images do not suffer recompression on each edit.
            if source.format == 'WEBP' and len(raw) <= 55_000 and source.width <= 720 and source.height <= 400:
                source.load()
                return 'data:image/webp;base64,' + base64.b64encode(raw).decode()
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((720, 400))
            for quality in (82, 65, 45):
                buffer = io.BytesIO()
                image.save(buffer, 'WEBP', quality=quality, method=4)
                if len(buffer.getvalue()) <= 55_000:
                    return 'data:image/webp;base64,' + base64.b64encode(buffer.getvalue()).decode()
        raise ValueError()
    except Exception:
        raise ValueError('Не удалось прочитать обложку. Выбери JPG, PNG или WebP.') from None


def find_covers(title):
    title = title.strip()
    if not 2 <= len(title) <= 200:
        raise HTTPException(422, 'Введи название от 2 до 200 символов.')
    query = urllib.parse.urlencode({'term': title, 'l': 'russian', 'cc': 'us'})
    try:
        with urllib.request.urlopen('https://store.steampowered.com/api/storesearch/?' + query, timeout=10) as response:
            payload = json.load(response)
        def cover(item):
            appid = item.get('id')
            if type(appid) is int and appid > 0 and item.get('name'):
                # New releases often use hashed asset URLs, not the legacy header path.
                store = _store(appid)
                image = (store or {}).get('header_image') or _image(item.get('tiny_image'))
                if image:
                    return {'title': str(item['name']), 'image': image}
            return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = [result for result in pool.map(cover, payload.get('items', [])[:8]) if result]
        return {'results': results}
    except Exception:
        raise HTTPException(502, 'Поиск обложек временно недоступен. Можно загрузить свою картинку.') from None
