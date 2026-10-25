import os
import json
import base64
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from threading import RLock
from config import DATA_DIR
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

VAPID_FILE = str(DATA_DIR / "vapid_keys.json")
SUBSCRIPTIONS_FILE = str(DATA_DIR / "push_subscriptions.json")
_subscription_lock = RLock()

_cached_vapid_keys: Optional[Dict[str, str]] = None

def _get_or_create_vapid_keys() -> Dict[str, str]:
    """Retrieves permanent VAPID keys from Upstash Redis or local file, creating them if not found."""
    global _cached_vapid_keys
    if _cached_vapid_keys:
        return _cached_vapid_keys

    configured_pem = os.getenv("VAPID_PRIVATE_KEY_PEM", "").replace("\\n", "\n")
    if configured_pem:
        v = Vapid.from_pem(configured_pem.encode("utf-8"))
        public = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        _cached_vapid_keys = {"private_pem": configured_pem, "public_b64": base64.urlsafe_b64encode(public).decode().rstrip("=")}
        return _cached_vapid_keys

    # 1. Try Upstash Redis
    try:
        from cloud_storage import get_cloud_data, is_cloud_configured
        if is_cloud_configured():
            cloud_keys = get_cloud_data("fitpulse_vapid_keys")
            if cloud_keys and isinstance(cloud_keys, dict) and "private_pem" in cloud_keys and "public_b64" in cloud_keys:
                _cached_vapid_keys = cloud_keys
                return _cached_vapid_keys
    except Exception as e:
        print(f"[VAPID] Cloud read note: {e}")

    # 2. Try local file
    if os.path.exists(VAPID_FILE):
        try:
            with open(VAPID_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "private_pem" in data and "public_b64" in data:
                    _cached_vapid_keys = data
                    # Sync to cloud if available
                    try:
                        from cloud_storage import set_cloud_data, is_cloud_configured
                        if is_cloud_configured():
                            set_cloud_data("fitpulse_vapid_keys", data)
                    except Exception:
                        pass
                    return _cached_vapid_keys
        except Exception as e:
            print(f"[VAPID] Local file read note: {e}")

    # 3. Generate new VAPID keys
    print("[VAPID] Generating new permanent VAPID keypair for Web Push...")
    v = Vapid()
    v.generate_keys()
    priv_pem = v.private_pem().decode("utf-8")
    pub_raw = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint
    )
    pub_b64 = base64.urlsafe_b64encode(pub_raw).decode("utf-8").rstrip("=")

    keys_data = {
        "private_pem": priv_pem,
        "public_b64": pub_b64
    }

    saved_local = False
    saved_cloud = False
    # Save to local file
    try:
        with open(VAPID_FILE, "w", encoding="utf-8") as f:
            json.dump(keys_data, f, indent=2)
        saved_local = True
    except Exception as e:
        print(f"[VAPID] Save local file error: {e}")

    # Save to Upstash Redis
    try:
        from cloud_storage import set_cloud_data, is_cloud_configured
        if is_cloud_configured():
            saved_cloud = set_cloud_data("fitpulse_vapid_keys", keys_data)
    except Exception as e:
        print(f"[VAPID] Save cloud error: {e}")

    if not (saved_local or saved_cloud):
        raise RuntimeError("VAPID keys could not be persisted; configure VAPID_PRIVATE_KEY_PEM")
    _cached_vapid_keys = keys_data
    return _cached_vapid_keys

def get_or_create_vapid_keys() -> Dict[str, str]:
    # Concurrent API requests must share one generated keypair.
    with _subscription_lock:
        return _get_or_create_vapid_keys()

def get_public_vapid_key() -> str:
    """Returns the URL-safe base64 encoded public key for the browser."""
    keys = get_or_create_vapid_keys()
    return keys["public_b64"]

def load_subscriptions() -> List[Dict[str, Any]]:
    """Loads all stored push subscriptions."""
    # 1. Try cloud
    try:
        from cloud_storage import get_cloud_data, is_cloud_configured
        if is_cloud_configured():
            subs = get_cloud_data("athlete_push_subscriptions")
            if isinstance(subs, list):
                return subs
    except Exception as e:
        print(f"[Push] Cloud subscriptions read note: {e}")

    # 2. Try local
    if os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
                subs = json.load(f)
                if isinstance(subs, list):
                    return subs
        except Exception:
            pass

    return []

def save_subscriptions(subs: List[Dict[str, Any]]):
    """Saves push subscriptions to local file and cloud."""
    saved_local = False
    # Local
    try:
        with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, indent=2)
        saved_local = True
    except Exception as e:
        print(f"[Push] Local subscriptions save error: {e}")

    # Cloud
    try:
        from cloud_storage import set_cloud_data, is_cloud_configured
        if is_cloud_configured():
            if not set_cloud_data("athlete_push_subscriptions", subs):
                raise RuntimeError("Push subscriptions could not be persisted in Redis")
            return
    except Exception as e:
        print(f"[Push] Cloud subscriptions save error: {e}")
        raise RuntimeError("Push subscription persistence failed") from e
    if not saved_local:
        raise RuntimeError("Push subscription persistence failed")

def validate_subscription(sub_info: Dict[str, Any]) -> bool:
    """Validate standard provider endpoint and encryption keys before storing."""
    try:
        endpoint = sub_info["endpoint"]
        if not isinstance(endpoint, str) or len(endpoint) > 4096:
            return False
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        allowed = ("push.apple.com", "fcm.googleapis.com", "updates.push.services.mozilla.com", "notify.windows.com")
        if parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment:
            return False
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            return False
        from cryptography.hazmat.primitives.asymmetric import ec
        def decode(value):
            return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        keys = sub_info["keys"]
        public = decode(keys["p256dh"])
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
        return len(decode(keys["auth"])) == 16
    except (KeyError, TypeError, ValueError):
        return False

def add_subscription(sub_info: Dict[str, Any]) -> bool:
    """Adds or updates a push subscription."""
    endpoint = sub_info.get("endpoint")
    if not validate_subscription(sub_info):
        return False

    with _subscription_lock:
        subs = load_subscriptions()
        filtered = [s for s in subs if s.get("endpoint") != endpoint]
        filtered.append({"endpoint": endpoint, "keys": sub_info["keys"]})
        save_subscriptions(filtered)
    print(f"[Push] Registered new Web Push subscription: {endpoint[:45]}...")
    return True

def remove_subscription(endpoint: str):
    """Removes an expired or unsubscribed endpoint."""
    with _subscription_lock:
        subs = load_subscriptions()
        updated = [s for s in subs if s.get("endpoint") != endpoint]
        if len(updated) != len(subs):
            save_subscriptions(updated)

def send_push_notification(
    title: str,
    body: str,
    url: str = "/?tab=chat",
    prompt: str = "",
    endpoint: Optional[str] = None,
    tag: str = "fitpulse",
) -> int:
    """Dispatches Web Push notification to all registered subscriptions."""
    subs = [s for s in load_subscriptions() if endpoint is None or s.get("endpoint") == endpoint]
    if not subs:
        print("[Push] No active Web Push subscriptions registered yet.")
        return 0

    keys = get_or_create_vapid_keys()
    priv_pem = keys["private_pem"]
    v = Vapid.from_pem(priv_pem.encode("utf-8"))

    payload = json.dumps({
        "tag": tag,
        "title": title,
        "body": body,
        "data": {
            "url": url,
            "prompt": prompt
        }
    })

    sent_count = 0
    expired_endpoints = []

    for sub in subs:
        endpoint = sub.get("endpoint", "")
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=v,
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:athlete@fitpulse.app")},
                timeout=10,
                ttl=3600
            )
            sent_count += 1
            print(f"[Push] Web Push successfully sent to {endpoint[:45]}...")
        except WebPushException as ex:
            print(f"[Push] Delivery error ({endpoint[:40]}): {ex}")
            # If subscription expired (404 or 410 Gone from Apple or Google)
            if ex.response is not None and ex.response.status_code in [404, 410]:
                expired_endpoints.append(endpoint)
        except Exception as e:
            print(f"[Push] Unexpected error: {e}")

    for exp in expired_endpoints:
        remove_subscription(exp)

    return sent_count
