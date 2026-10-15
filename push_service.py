import os
import json
import base64
from typing import Optional, List, Dict, Any
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

VAPID_FILE = "vapid_keys.json"
SUBSCRIPTIONS_FILE = "push_subscriptions.json"

_cached_vapid_keys: Optional[Dict[str, str]] = None

def get_or_create_vapid_keys() -> Dict[str, str]:
    """Retrieves permanent VAPID keys from Upstash Redis or local file, creating them if not found."""
    global _cached_vapid_keys
    if _cached_vapid_keys:
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

    # Save to local file
    try:
        with open(VAPID_FILE, "w", encoding="utf-8") as f:
            json.dump(keys_data, f, indent=2)
    except Exception as e:
        print(f"[VAPID] Save local file error: {e}")

    # Save to Upstash Redis
    try:
        from cloud_storage import set_cloud_data, is_cloud_configured
        if is_cloud_configured():
            set_cloud_data("fitpulse_vapid_keys", keys_data)
    except Exception as e:
        print(f"[VAPID] Save cloud error: {e}")

    _cached_vapid_keys = keys_data
    return _cached_vapid_keys

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
            if subs and isinstance(subs, list):
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
    # Local
    try:
        with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, indent=2)
    except Exception as e:
        print(f"[Push] Local subscriptions save error: {e}")

    # Cloud
    try:
        from cloud_storage import set_cloud_data, is_cloud_configured
        if is_cloud_configured():
            set_cloud_data("athlete_push_subscriptions", subs)
    except Exception as e:
        print(f"[Push] Cloud subscriptions save error: {e}")

def add_subscription(sub_info: Dict[str, Any]) -> bool:
    """Adds or updates a push subscription."""
    endpoint = sub_info.get("endpoint")
    if not endpoint:
        return False

    subs = load_subscriptions()
    # Filter out existing with same endpoint
    filtered = [s for s in subs if s.get("endpoint") != endpoint]
    filtered.append(sub_info)
    save_subscriptions(filtered)
    print(f"[Push] Registered new Web Push subscription: {endpoint[:45]}...")
    return True

def remove_subscription(endpoint: str):
    """Removes an expired or unsubscribed endpoint."""
    subs = load_subscriptions()
    updated = [s for s in subs if s.get("endpoint") != endpoint]
    if len(updated) != len(subs):
        save_subscriptions(updated)
        print(f"[Push] Removed expired Web Push subscription: {endpoint[:45]}...")

def send_push_notification(
    title: str,
    body: str,
    url: str = "/?tab=chat",
    prompt: str = ""
) -> int:
    """Dispatches Web Push notification to all registered subscriptions."""
    subs = load_subscriptions()
    if not subs:
        print("[Push] No active Web Push subscriptions registered yet.")
        return 0

    keys = get_or_create_vapid_keys()
    priv_pem = keys["private_pem"]

    payload = json.dumps({
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
                vapid_private_key=priv_pem,
                vapid_claims={"sub": "mailto:athlete@fitpulse.app"},
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
