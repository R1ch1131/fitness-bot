"""Personal games and watchlist, independent of workout integrations."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cloud_storage import CloudStorageError, get_cloud_data, set_cloud_data, is_cloud_configured
from config import DATA_DIR
from catalog import CatalogInfo


class MediaInput(BaseModel):
    catalog: CatalogInfo | None = None
    title: str = Field(min_length=1, max_length=200)
    kind: Literal['game', 'movie', 'series', 'anime']
    status: Literal['planned', 'active', 'finished'] = 'planned'
    progress: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, gt=0)
    rating: float | None = Field(default=None, ge=0, le=10)
    notes: str = Field(default='', max_length=10000)
    cover_image: str | None = Field(default=None, max_length=3_000_000)

    @model_validator(mode='after')
    def normalize(self):
        from media_covers import normalize_cover
        if 'cover_image' in self.model_fields_set:
            self.cover_image = normalize_cover(self.cover_image)
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Укажи название')
        if self.kind == 'game':
            self.total = 100
        elif self.kind == 'movie':
            self.total = None
            self.progress = 0
        if self.total is not None and self.progress > self.total:
            raise ValueError('Прогресс не может превышать общее количество')
        if self.status == 'finished' and self.total is not None:
            self.progress = self.total
        elif self.total is not None and self.progress == self.total:
            self.status = 'finished'
        elif self.progress > 0:
            self.status = 'active'
        return self


class MediaBackupItem(MediaInput):
    model_config = ConfigDict(extra='allow')
    id: str = Field(min_length=1, max_length=100)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), max_length=100)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), max_length=100)


class RestoreMediaInput(BaseModel):
    items: list[MediaBackupItem] = Field(max_length=5000)

    @model_validator(mode='after')
    def unique_ids(self):
        ids = [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError('В резервной копии повторяются идентификаторы')
        return self


class MediaLibrary:
    def __init__(self, path: Path = DATA_DIR / 'media.json'):
        self.path = path
        self.lock = RLock()
        self.loaded = False
        self._snapshot = []

    @staticmethod
    def _validate_stored(items):
        if not isinstance(items, list) or any(not isinstance(item, dict) or not item.get('id') or item.get('kind') not in ('game', 'movie', 'series', 'anime') for item in items):
            raise HTTPException(503, 'Коллекция в хранилище повреждена. Изменения заблокированы, чтобы сохранить данные.')
        return items

    def _write_local(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def _read_cloud(self):
        try:
            return get_cloud_data('athlete_media', strict=is_cloud_configured())
        except CloudStorageError:
            raise HTTPException(503, 'Не удалось загрузить коллекцию из Upstash. Сохранённая копия не изменена. Повтори попытку позже.') from None

    def items(self):
        with self.lock:
            if self.loaded:
                return deepcopy(self._snapshot)
            cloud = self._read_cloud()
            if cloud is not None:
                items = self._validate_stored(cloud)
                try:
                    self._write_local(items)
                except OSError:
                    if not is_cloud_configured():
                        raise
            else:
                try:
                    items = self._validate_stored(json.loads(self.path.read_text(encoding='utf-8'))) if self.path.exists() else []
                except (OSError, ValueError):
                    raise HTTPException(503, 'Не удалось прочитать локальную коллекцию. Восстанови резервную копию.') from None
                # Migrate existing local entries only after a confirmed missing Redis key.
                if items and is_cloud_configured() and not set_cloud_data('athlete_media', items):
                    raise HTTPException(503, 'Не удалось перенести коллекцию в Upstash. Локальная копия сохранена; повтори попытку.')
            self._snapshot = deepcopy(items)
            self.loaded = True
            return deepcopy(items)

    def _save(self, items):
        # Confirm the same Redis used by books before reporting a successful mutation.
        cloud_saved = set_cloud_data('athlete_media', items)
        if is_cloud_configured() and not cloud_saved:
            raise HTTPException(503, 'Upstash не подтвердил сохранение. Изменение не применено — повтори попытку. Данные формы сохранены.')
        try:
            self._write_local(items)
        except OSError:
            if not is_cloud_configured():
                raise HTTPException(503, 'Не удалось сохранить коллекцию на сервере. Изменение не применено.') from None
        self._snapshot = deepcopy(items)
        self.loaded = True

    def storage_status(self):
        if not is_cloud_configured():
            return {'backend': 'local', 'state': 'not_configured', 'message': 'Upstash не подключён. На Render данные могут потеряться при обновлении. Скачай резервную копию.'}
        cloud = self._read_cloud()
        if cloud is not None:
            self._validate_stored(cloud)
        return {'backend': 'upstash', 'state': 'verified', 'count': len(cloud or []), 'message': 'Upstash отвечает. Сохранение изменений подтверждается базой.'}

    def restore(self, value: RestoreMediaInput):
        with self.lock:
            # A restore is explicit, but must not overwrite a temporarily unreachable cloud.
            self._read_cloud()
            items = [item.model_dump() for item in value.items]
            self._save(items)
            return {'items': items}

    def save(self, value: MediaInput, item_id: str | None = None):
        with self.lock:
            items = self.items()
            old = next((item for item in items if item['id'] == item_id), None)
            if item_id is not None and old is None:
                raise HTTPException(404, 'Запись не найдена')
            now = datetime.now(timezone.utc).isoformat()
            item = {**(old or {}), **value.model_dump(), 'id': item_id or str(uuid4()),
                    'created_at': old['created_at'] if old else now, 'updated_at': now}
            if old and 'cover_image' not in value.model_fields_set:
                item['cover_image'] = old.get('cover_image')
            if old and 'catalog' not in value.model_fields_set:
                item['catalog'] = old.get('catalog')
            if value.kind != 'game':
                item = {key: val for key, val in item.items() if not key.startswith('steam_')}
            items = [item if entry['id'] == item_id else entry for entry in items] if old else [*items, item]
            self._save(items)
            return {'items': items}

    def sync_steam(self, steam_id, games):
        with self.lock:
            items = self.items()
            added = updated = 0
            now = datetime.now(timezone.utc).isoformat()
            for game in games:
                existing = next((item for item in items if item['kind'] == 'game'
                                 and item.get('steam_appid') == game['appid']
                                 and item.get('steam_id') == steam_id), None)
                if existing is None:
                    # Link a single manually added game without resetting its personal fields.
                    matches = [item for item in items if item['kind'] == 'game'
                               and not item.get('steam_appid')
                               and item['title'].strip().casefold() == game['name'].casefold()]
                    existing = matches[0] if len(matches) == 1 else None
                if existing is None:
                    existing = {**MediaInput(title=game['name'], kind='game', status='active').model_dump(),
                                'id': str(uuid4()), 'created_at': now}
                    items.append(existing)
                    added += 1
                else:
                    updated += 1
                existing.update(steam_appid=game['appid'], steam_id=steam_id,
                                steam_playtime_minutes=game['minutes'], steam_synced_at=now, updated_at=now)
                if 'rtime_last_played' in game:
                    existing['steam_last_played'] = game['rtime_last_played']
                if 'playtime_2weeks' in game:
                    existing['steam_recent_minutes'] = game['playtime_2weeks']
            if games:
                self._save(items)
            return {'items': items, 'steam_sync': {'added': added, 'updated': updated, 'matched': len(games)}}

    def delete(self, item_id: str):
        with self.lock:
            items = self.items()
            if not any(item['id'] == item_id for item in items):
                raise HTTPException(404, 'Запись не найдена')
            items = [item for item in items if item['id'] != item_id]
            self._save(items)
            return {'items': items}

    def game_details(self, item_id):
        from steam_details import get_game_details
        item = next((item for item in self.items() if item['id'] == item_id), None)
        if not item or item['kind'] != 'game' or not item.get('steam_appid'):
            raise HTTPException(404, 'Для этой записи нет данных Steam')
        result = get_game_details(item['steam_appid'], item.get('steam_id', ''))
        # Keep a small summary for library cards; full achievement lists stay cached.
        with self.lock:
            items = self.items()
            current = next((entry for entry in items if entry['id'] == item_id), None)
            if current and current.get('steam_appid') == item['steam_appid'] and current.get('steam_id') == item.get('steam_id'):
                summary = {}
                if result['store']:
                    summary['steam_header_image'] = result['store']['header_image']
                    summary['steam_genres'] = result['store']['genres']
                achievement = result['achievements']
                if achievement['state'] == 'ready':
                    summary['steam_achievements'] = {key: achievement[key] for key in ('unlocked', 'total')}
                if any(current.get(key) != value for key, value in summary.items()):
                    current.update(summary)
                    self._save(items)
        return result


library = MediaLibrary()
router = APIRouter(prefix='/api/media', tags=['media'])


@router.get('')
def list_media():
    return {'items': library.items(), 'storage': {'backend': 'upstash' if is_cloud_configured() else 'local', 'state': 'configured' if is_cloud_configured() else 'not_configured'}}


@router.post('')
def create_media(value: MediaInput):
    return library.save(value)


@router.get('/covers')
def search_covers(title: str = Query(min_length=2, max_length=200)):
    from media_covers import find_covers
    return find_covers(title)


@router.get('/storage')
def storage_status():
    return library.storage_status()


@router.post('/restore')
def restore_media(value: RestoreMediaInput):
    return library.restore(value)


@router.post('/steam/sync')
def sync_steam():
    from steam_client import get_played_games
    steam_id, games = get_played_games()
    return library.sync_steam(steam_id, games)


@router.put('/{item_id}')
def update_media(item_id: str, value: MediaInput):
    return library.save(value, item_id)


@router.get('/{item_id}/details')
def game_details(item_id: str):
    return library.game_details(item_id)


@router.delete('/{item_id}')
def delete_media(item_id: str):
    return library.delete(item_id)
