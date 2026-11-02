"""Personal games and watchlist, independent of workout integrations."""
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from cloud_storage import get_cloud_data, set_cloud_data
from config import DATA_DIR


class MediaInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal['game', 'movie', 'series', 'anime']
    status: Literal['planned', 'active', 'finished'] = 'planned'
    progress: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, gt=0)
    rating: float | None = Field(default=None, ge=0, le=10)
    notes: str = Field(default='', max_length=10000)

    @model_validator(mode='after')
    def normalize(self):
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


class MediaLibrary:
    def __init__(self, path: Path = DATA_DIR / 'media.json'):
        self.path = path
        self.lock = RLock()
        self.loaded = False

    def items(self):
        with self.lock:
            if not self.loaded:
                cloud = get_cloud_data('athlete_media')
                if isinstance(cloud, list):
                    self.path.write_text(json.dumps(cloud, ensure_ascii=False), encoding='utf-8')
                self.loaded = True
            if not self.path.exists():
                return []
            return json.loads(self.path.read_text(encoding='utf-8'))

    def _save(self, items):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)
        set_cloud_data('athlete_media', items)

    def save(self, value: MediaInput, item_id: str | None = None):
        with self.lock:
            items = self.items()
            old = next((item for item in items if item['id'] == item_id), None)
            if item_id is not None and old is None:
                raise HTTPException(404, 'Запись не найдена')
            now = datetime.now(timezone.utc).isoformat()
            item = {**value.model_dump(), 'id': item_id or str(uuid4()),
                    'created_at': old['created_at'] if old else now, 'updated_at': now}
            items = [item if entry['id'] == item_id else entry for entry in items] if old else [*items, item]
            self._save(items)
            return {'items': items}

    def delete(self, item_id: str):
        with self.lock:
            items = self.items()
            if not any(item['id'] == item_id for item in items):
                raise HTTPException(404, 'Запись не найдена')
            items = [item for item in items if item['id'] != item_id]
            self._save(items)
            return {'items': items}


library = MediaLibrary()
router = APIRouter(prefix='/api/media', tags=['media'])


@router.get('')
def list_media():
    return {'items': library.items()}


@router.post('')
def create_media(value: MediaInput):
    return library.save(value)


@router.put('/{item_id}')
def update_media(item_id: str, value: MediaInput):
    return library.save(value, item_id)


@router.delete('/{item_id}')
def delete_media(item_id: str):
    return library.delete(item_id)
