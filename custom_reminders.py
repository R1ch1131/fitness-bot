"""Personal, recurring PWA reminders; no dependency on the browser being open."""
import copy
import re
import uuid
from datetime import datetime, timedelta
from notification_settings import _read, _write, _lock, TZ, CATCH_UP_SECONDS

_accepted = set()


def validate_reminder(value):
    fields = {"title", "body", "time", "weekdays", "enabled"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Укажите название, текст, время, дни недели и состояние напоминания")
    if not isinstance(value["title"], str) or not 1 <= len(value["title"].strip()) <= 80:
        raise ValueError("Название должно содержать от 1 до 80 символов")
    if not isinstance(value["body"], str) or len(value["body"]) > 240:
        raise ValueError("Текст должен быть не длиннее 240 символов")
    if not isinstance(value["time"], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value["time"]):
        raise ValueError("Укажите время в формате ЧЧ:ММ")
    days = value["weekdays"]
    if not isinstance(days, list) or not days or any(type(day) is not int or not 0 <= day <= 6 for day in days) or len(set(days)) != len(days):
        raise ValueError("Выберите хотя бы один день недели")
    if type(value["enabled"]) is not bool:
        raise ValueError("Некорректное состояние напоминания")
    return {"title": value["title"].strip(), "body": value["body"].strip(), "time": value["time"], "weekdays": sorted(days), "enabled": value["enabled"]}


def _document():
    return _read("custom_reminders", {"items": [], "delivery": {}})


def _due(item, day):
    hour, minute = map(int, item["time"].split(":"))
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _sent(document, identifier, due):
    return due.isoformat() in document.get("delivery", {}).get(identifier, {}) or (identifier, due.isoformat()) in _accepted


def _eligible(item, due):
    return due.weekday() in item["weekdays"] and due >= datetime.fromisoformat(item["created_at"])


def list_reminders(now=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    with _lock:
        document = copy.deepcopy(_document())
    result = []
    for item in document["items"]:
        next_run = None
        if item["enabled"]:
            for offset in range(-1, 8):
                due = _due(item, now + timedelta(days=offset))
                if _eligible(item, due) and due > now - timedelta(seconds=CATCH_UP_SECONDS) and not _sent(document, item["id"], due):
                    next_run = due.isoformat()
                    break
        result.append({**item, "next_run": next_run})
    return result


def create_reminder(value, now=None):
    value = validate_reminder(value)
    now = (now or datetime.now(TZ)).astimezone(TZ)
    with _lock:
        document = _document()
        if len(document["items"]) >= 50:
            raise ValueError("Можно добавить до 50 собственных напоминаний")
        item = {**value, "id": uuid.uuid4().hex, "created_at": now.isoformat()}
        document["items"].append(item)
        _write("custom_reminders", document)
    return item


def update_reminder(identifier, value):
    value = validate_reminder(value)
    with _lock:
        document = _document()
        for item in document["items"]:
            if item["id"] == identifier:
                item.update(value)
                _write("custom_reminders", document)
                return item
    raise KeyError(identifier)


def delete_reminder(identifier):
    with _lock:
        document = _document()
        items = [item for item in document["items"] if item["id"] != identifier]
        if len(items) == len(document["items"]):
            raise KeyError(identifier)
        document["items"] = items
        document.setdefault("delivery", {}).pop(identifier, None)
        _write("custom_reminders", document)
        _accepted.difference_update({entry for entry in _accepted if entry[0] == identifier})


def dispatch_custom_pushes(now=None):
    from push_service import send_push_notification
    now = (now or datetime.now(TZ)).astimezone(TZ)
    with _lock:
        snapshot = copy.deepcopy(_document())
    for item in snapshot["items"]:
        due = _due(item, now)
        if due > now:
            due -= timedelta(days=1)
        if not item["enabled"] or not _eligible(item, due) or not 0 <= (now - due).total_seconds() < CATCH_UP_SECONDS:
            continue
        key = (item["id"], due.isoformat())
        with _lock:
            document = _document()
            current = next((entry for entry in document["items"] if entry["id"] == item["id"]), None)
            if current != item or due.isoformat() in document.get("delivery", {}).get(item["id"], {}):
                continue
        if key not in _accepted:
            if not send_push_notification(item["title"], item["body"] or item["title"], url="/", tag="custom-" + item["id"]):
                continue
            _accepted.add(key)
        with _lock:
            document = _document()
            if any(entry["id"] == item["id"] for entry in document["items"]):
                records = document.setdefault("delivery", {}).setdefault(item["id"], {})
                records[due.isoformat()] = now.isoformat()
                document["delivery"][item["id"]] = dict(sorted(records.items())[-32:])
                _write("custom_reminders", document)
            _accepted.discard(key)
