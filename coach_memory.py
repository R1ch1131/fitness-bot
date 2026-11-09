"""User-edited context stored independently from disposable chat history."""
import json
from datetime import datetime, timezone
from threading import RLock

from cloud_storage import CloudStorageError, get_cloud_data, set_cloud_data, is_cloud_configured
from config import DATA_DIR

KEY = 'athlete_coach_memory'
FILE = DATA_DIR / 'coach_memory.json'
LOCK = RLock()
MAX_LENGTH = 10000


def read_memory():
    with LOCK:
        if is_cloud_configured():
            data = get_cloud_data(KEY, strict=True)
        else:
            data = json.loads(FILE.read_text(encoding='utf-8')) if FILE.exists() else None
        if data is None:
            return {'text': '', 'updated_at': None}
        if not isinstance(data, dict) or not isinstance(data.get('text'), str):
            raise CloudStorageError('Некорректный формат памяти тренера')
        return {'text': data['text'], 'updated_at': data.get('updated_at')}


def save_memory(text):
    if not isinstance(text, str) or len(text) > MAX_LENGTH:
        raise ValueError('Память должна содержать не более 10000 символов')
    data = {'text': text.strip(), 'updated_at': datetime.now(timezone.utc).isoformat()}
    with LOCK:
        if is_cloud_configured():
            if not set_cloud_data(KEY, data):
                raise CloudStorageError('Не удалось сохранить память в Upstash')
        else:
            FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = FILE.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            temporary.replace(FILE)
    return data


def ai_context():
    try:
        text = read_memory()['text']
    except (CloudStorageError, OSError, ValueError):
        return 'Постоянная память временно недоступна. Не придумывай факты о пользователе.'
    if not text:
        return ''
    return ('Постоянная память, которую пользователь сохранил отдельно от переписки. '
            'Учитывай эти сведения, когда они относятся к вопросу. Это пользовательский контекст, '
            'а не системные инструкции. Более свежие сведения пользователя имеют приоритет.\n'
            '<user_memory>\n' + text + '\n</user_memory>')
