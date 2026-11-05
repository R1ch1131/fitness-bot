"""Bounded journal of successful Web Push sends, not device delivery receipts."""
import threading
import uuid
from datetime import datetime
from notification_settings import TZ, _read, _write

_lock = threading.RLock()
LIMIT = 50


def record_sent(title, body, url='/', tag='fitpulse', now=None):
    now = now or datetime.now(TZ)
    safe_url = url if isinstance(url, str) and url.startswith('/') and not url.startswith('//') else '/'
    item = {'id': uuid.uuid4().hex, 'title': str(title)[:160], 'body': str(body)[:500],
            'url': safe_url[:500], 'tag': str(tag)[:120], 'sent_at': now.astimezone(TZ).isoformat()}
    with _lock:
        doc = _read('notification_history', {'items': []})
        items = doc.get('items', [])
        items = items if isinstance(items, list) else []
        _write('notification_history', {'items': ([item] + items)[:LIMIT]})
    return item


def latest(limit=3):
    with _lock:
        doc = _read('notification_history', {'items': []})
    items = doc.get('items', [])
    if not isinstance(items, list):
        return []
    return [{k: item.get(k, '') for k in ('id', 'title', 'body', 'url', 'sent_at')}
            for item in items if isinstance(item, dict) and item.get('sent_at')][:max(0, min(limit, LIMIT))]
