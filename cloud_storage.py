import os
import json
import urllib.request
from typing import Any, Optional

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

def is_cloud_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)

def get_cloud_data(key: str) -> Optional[Any]:
    if not is_cloud_configured():
        return None
    try:
        url = f"{UPSTASH_URL.rstrip('/')}/get/{key}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
            result = raw.get("result")
            if result is not None:
                if isinstance(result, str):
                    try:
                        return json.loads(result)
                    except Exception:
                        return result
                return result
    except Exception as e:
        print(f"Cloud storage get error [{key}]: {e}")
    return None

def set_cloud_data(key: str, value: Any) -> bool:
    if not is_cloud_configured():
        return False
    try:
        url = f"{UPSTASH_URL.rstrip('/')}/set/{key}"
        payload = json.dumps(value, ensure_ascii=False)
        req = urllib.request.Request(
            url,
            data=payload.encode('utf-8'),
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "text/plain; charset=utf-8"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"Cloud storage set error [{key}]: {e}")
        return False
