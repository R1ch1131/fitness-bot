"""Cloud chat history, with server messages preserved during client backups."""
import json
from pathlib import Path
from threading import RLock
from cloud_storage import get_cloud_data, set_cloud_data, is_cloud_configured, CloudStorageError

FILE = Path('chat_history.json')
KEY = 'athlete_chat_history'
LOCK = RLock()


def read_history():
    with LOCK:
        data = get_cloud_data(KEY, strict=True) if is_cloud_configured() else json.loads(FILE.read_text(encoding='utf-8')) if FILE.exists() else []
        if data is None:
            return []
        if not isinstance(data, list):
            raise CloudStorageError('Некорректная история чата')
        return data


def _write(messages):
    if is_cloud_configured():
        if not set_cloud_data(KEY, messages):
            raise CloudStorageError('История не сохранена в Upstash')
    else:
        temporary = FILE.with_suffix('.tmp')
        temporary.write_text(json.dumps(messages, ensure_ascii=False), encoding='utf-8')
        temporary.replace(FILE)


def save_history(messages, *, clear=False):
    if not isinstance(messages, list) or len(messages) > 1000:
        raise ValueError('Некорректные сообщения')
    clean = []
    for item in messages[-100:]:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item.get('sender') not in ('user', 'coach') or not isinstance(item.get('text'), str) or len(item['text']) > 50000:
            raise ValueError('Некорректное сообщение')
        clean.append(item)
    with LOCK:
        stored = [] if clear else read_history()
        # An older phone snapshot must never erase a proactive message.
        merged = {item['id']: item for item in stored if isinstance(item, dict) and isinstance(item.get('id'), str)}
        for item in clean:
            if item['id'].startswith('evening-') and item['id'] in merged:
                continue
            merged[item['id']] = item
        result = list(merged.values())[-100:]
        _write(result)
        return result


def append_message(message):
    return save_history([message])
