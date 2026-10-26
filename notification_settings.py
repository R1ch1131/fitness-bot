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


def dispatch_scheduled_push(now=None):
    global _delivery_memory
    from push_service import send_push_notification
    now = (now or datetime.now(TZ)).astimezone(TZ)
    settings = get_settings()
    with _lock:
        if _delivery_memory is None:
            _delivery_memory = _read("notification_delivery", {})
        sent = _delivery_memory
    for name, (title, body, tab) in MESSAGES.items():
        item = settings[name]
        if not item["enabled"] or (name == "gym" and now.weekday() >= 5) or (name == "weekly" and now.weekday() != 6):
            continue
        hour, minute = map(int, item["time"].split(":"))
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Allow a small catch-up window after a brief restart, never hours-old reminders.
        if not 0 <= (now - due).total_seconds() < 300 or sent.get(name) == now.date().isoformat():
            continue
        if send_push_notification(title, body, url=f"/?tab={tab}", tag=name + "-reminder"):
            sent[name] = now.date().isoformat()
            with _lock:
                _write("notification_delivery", sent)


def start_push_scheduler():
    def worker():
        from push_test_queue import dispatch_test_pushes
        while True:
            for dispatch in (dispatch_scheduled_push, dispatch_test_pushes):
                try:
                    dispatch()
                except Exception as exc:
                    print(f"[Push] Scheduler: {exc}")
            time.sleep(20)
    threading.Thread(target=worker, daemon=True, name="pwa-notifications").start()
