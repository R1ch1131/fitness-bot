"""Personal PWA notification preferences. Telegram keeps its own schedule."""
import copy
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from config import DATA_DIR

TZ = timezone(timedelta(hours=6))
DEFAULTS = {
    "gym": {"enabled": True, "time": "08:30"},
    "laundry": {"enabled": True, "time": "22:00"},
    "nutrition": {"enabled": True, "time": "23:00"},
    "weekly": {"enabled": True, "time": "12:00"},
    "checkin": {"enabled": True, "delay_minutes": 20},
}
_lock = threading.RLock()
_delivery_memory = None
_delivery_dirty = False
_last_schedule_check = None
CATCH_UP_SECONDS = 3600


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Укажите настройки всех пяти типов уведомлений")
    result = {}
    for name, default in DEFAULTS.items():
        item = value[name]
        if not isinstance(item, dict) or set(item) != set(default) or type(item.get("enabled")) is not bool:
            raise ValueError("Некорректные настройки уведомления")
        if name == "checkin":
            delay = item.get("delay_minutes")
            if type(delay) is not int or not 5 <= delay <= 120:
                raise ValueError("Задержка опроса должна быть от 5 до 120 минут")
        elif not isinstance(item.get("time"), str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item["time"]):
            raise ValueError("Время должно быть в формате ЧЧ:ММ")
        result[name] = dict(item)
    return result


def _read(name, default):
    from cloud_storage import get_cloud_data, is_cloud_configured
    if is_cloud_configured():
        value = get_cloud_data("fitpulse_" + name)
        if isinstance(value, dict):
            return value
    try:
        value = json.loads((DATA_DIR / (name + ".json")).read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
    except (OSError, ValueError):
        pass
    return copy.deepcopy(default)


def _write(name, value):
    from cloud_storage import set_cloud_data, is_cloud_configured
    # Cloud failure must not be reported as a successful settings save.
    if is_cloud_configured() and not set_cloud_data("fitpulse_" + name, value):
        raise RuntimeError("Не удалось сохранить настройки в облаке. Повторите попытку.")
    target = DATA_DIR / (name + ".json")
    temporary = target.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
    except OSError:
        if not is_cloud_configured():
            raise


def get_settings():
    with _lock:
        return validate_settings(_read("notification_settings", DEFAULTS))


def save_settings(value):
    settings = validate_settings(value)
    with _lock:
        # Bind legacy date-only records to their old time before saving a new time.
        _load_delivery(get_settings())
        _flush_delivery()
        _write("notification_settings", settings)
    return settings


def checkin_due_time(pending, settings):
    end_time = pending.get("end_time")
    try:
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=TZ)
        finished = end.timestamp()
    except (AttributeError, TypeError, ValueError):
        finished = pending.get("due_time", 0) - 20 * 60
    return finished + settings["checkin"]["delay_minutes"] * 60


def dispatch_workout_push(pending, now):
    if not pending or pending.get("responded") or pending.get("push_sent"):
        return 0
    settings = get_settings()
    due = checkin_due_time(pending, settings)
    if not settings["checkin"]["enabled"] or not due <= now <= due + 8 * 3600:
        return 0
    from push_service import send_push_notification
    return send_push_notification(
        "Как прошла тренировка? 💪",
        f"После «{pending.get('workout_title', 'Тренировка')}» прошло {settings['checkin']['delay_minutes']} мин. Расскажи, как самочувствие.",
        url="/?tab=chat", tag=f"workout-{pending.get('workout_id')}",
    )


MESSAGES = {
    "gym": ("Пора в зал", "Не забудь сменные вещи и тапочки!", "workouts"),
    "laundry": ("FitPulse", "Вещи после тренировки постирал?", "dashboard"),
    "nutrition": ("Вечерняя проверка питания", "Проверь калории и БЖУ за сегодня.", "dashboard"),
    "weekly": ("Недельный отчёт", "Посмотри итоги тренировок и питания за неделю.", "weekly"),
}


def _allowed_day(name, day):
    return not ((name == "gym" and day.weekday() >= 5) or (name == "weekly" and day.weekday() != 6))


def _load_delivery(settings):
    global _delivery_memory, _delivery_dirty
    if _delivery_memory is None:
        _delivery_memory = _read("notification_delivery", {})
    # Older versions only stored YYYY-MM-DD, which blocked every new time that day.
    for name in MESSAGES:
        legacy = _delivery_memory.get(name)
        if isinstance(legacy, str):
            _delivery_memory[name] = {"scheduled_for": f"{legacy}T{settings[name]['time']}:00+06:00", "accepted_at": None}
            _delivery_dirty = True
    return _delivery_memory


def _flush_delivery():
    global _delivery_dirty
    if _delivery_dirty:
        _write("notification_delivery", _delivery_memory)
        _delivery_dirty = False


def _already_sent(records, name, due):
    record = records.get(name)
    return isinstance(record, dict) and (record.get("scheduled_for") == due.isoformat() or due.isoformat() in record.get("recent", {}))


def schedule_status(settings=None, now=None):
    """User-facing next run and accepted-at times; never expose subscription keys."""
    settings = settings or get_settings()
    now = (now or datetime.now(TZ)).astimezone(TZ)
    with _lock:
        records = copy.deepcopy(_load_delivery(settings))
    items = {}
    for name in MESSAGES:
        item = settings[name]
        next_run = None
        if item["enabled"]:
            hour, minute = map(int, item["time"].split(":"))
            for offset in range(-1, 8):
                day = now + timedelta(days=offset)
                due = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if _allowed_day(name, day) and due > now - timedelta(seconds=CATCH_UP_SECONDS) and not _already_sent(records, name, due):
                    next_run = due.isoformat()
                    break
        record = records.get(name)
        items[name] = {"next_run": next_run, "last_accepted_at": record.get("accepted_at") if isinstance(record, dict) else None}
    return {"server_time": now.isoformat(), "timezone": "Asia/Omsk", "last_checked_at": _last_schedule_check, "items": items}


def dispatch_scheduled_push(now=None):
    global _delivery_dirty, _last_schedule_check
    from push_service import send_push_notification
    now = (now or datetime.now(TZ)).astimezone(TZ)
    settings = get_settings()
    _last_schedule_check = now.isoformat()
    with _lock:
        sent = _load_delivery(settings)
        # Retry journal writes after a storage failure without sending the push twice.
        _flush_delivery()
    for name, (title, body, tab) in MESSAGES.items():
        item = settings[name]
        if not item["enabled"]:
            continue
        hour, minute = map(int, item["time"].split(":"))
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Include yesterday near midnight; do not lose a late 23:xx notification.
        if due > now:
            due -= timedelta(days=1)
        if not _allowed_day(name, due) or not 0 <= (now - due).total_seconds() < CATCH_UP_SECONDS or _already_sent(sent, name, due):
            continue
        if send_push_notification(title, body, url=f"/?tab={tab}", tag=name + "-reminder"):
            with _lock:
                previous = sent.get(name)
                recent = dict(previous.get("recent", {})) if isinstance(previous, dict) else {}
                if isinstance(previous, dict) and previous.get("scheduled_for"):
                    recent[previous["scheduled_for"]] = previous.get("accepted_at")
                recent[due.isoformat()] = now.isoformat()
                recent = dict(sorted(recent.items())[-32:])
                sent[name] = {"scheduled_for": due.isoformat(), "accepted_at": now.isoformat(), "recent": recent}
                _delivery_dirty = True
                _flush_delivery()


def start_push_scheduler():
    def worker():
        from push_test_queue import dispatch_test_pushes
        from custom_reminders import dispatch_custom_pushes
        while True:
            for dispatch in (dispatch_scheduled_push, dispatch_custom_pushes, dispatch_test_pushes):
                try:
                    dispatch()
                except Exception as exc:
                    print(f"[Push] Scheduler: {exc}")
            time.sleep(20)
    threading.Thread(target=worker, daemon=True, name="pwa-notifications").start()
