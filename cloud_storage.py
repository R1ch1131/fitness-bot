import os
import json
import urllib.request
from typing import Any, Optional

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

def is_cloud_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)

class CloudStorageError(RuntimeError):
    """A missing key and a failed cloud read must not be treated alike."""


def get_cloud_data(key: str, *, strict: bool = False) -> Optional[Any]:
    if not is_cloud_configured():
        return None
    try:
        url = UPSTASH_URL.rstrip('/')
        cmd = ["GET", key]
        req = urllib.request.Request(
            url,
            data=json.dumps(cmd).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
            if not isinstance(raw, dict) or 'error' in raw or 'result' not in raw:
                raise CloudStorageError('Облако вернуло ошибку чтения')
            result = raw.get("result")
            if result is not None:
                if isinstance(result, str):
                    try:
                        return json.loads(result)
                    except (ValueError, TypeError):
                        if strict:
                            raise CloudStorageError('Некорректные данные в облаке') from None
                        return result
                return result
    except Exception as e:
        if strict:
            raise CloudStorageError('Не удалось прочитать данные из Upstash') from None
        print(f"Cloud storage get error [{key}]: {type(e).__name__}")
    return None

def set_cloud_data(key: str, value: Any) -> bool:
    if not is_cloud_configured():
        return False
    try:
        url = UPSTASH_URL.rstrip('/')
        val_str = json.dumps(value, ensure_ascii=True)
        cmd = ["SET", key, val_str]
        req = urllib.request.Request(
            url,
            data=json.dumps(cmd).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
            return raw.get("result") == "OK"
    except Exception as e:
        print(f"Cloud storage set error [{key}]: {e}")
        return False
