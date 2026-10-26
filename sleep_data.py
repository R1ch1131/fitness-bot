"""Explicit, authenticated Apple Health imports. No access to iCloud or HealthKit."""
import hmac
import os
import re
import threading
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from notification_settings import TZ, _read, _write

_lock = threading.RLock()
STAGES = {"core", "deep", "rem", "asleep", "awake", "in_bed"}
ALIASES = {"0": "in_bed", "1": "asleep", "2": "awake", "3": "core", "4": "deep", "5": "rem",
           "asleepcore": "core", "asleepdeep": "deep", "asleeprem": "rem", "asleepunspecified": "asleep",
           "inbed": "in_bed", "базовый": "core", "глубокий": "deep", "быстрый": "rem",
           "сон": "asleep", "бодрствование": "awake", "в постели": "in_bed"}


def is_configured():
    return len(os.environ.get("HEALTH_IMPORT_TOKEN", "")) >= 32


def authorize(header):
    if not is_configured():
        raise RuntimeError("Добавьте HEALTH_IMPORT_TOKEN (не менее 32 символов) в настройки сервера")
    expected = "Bearer " + os.environ["HEALTH_IMPORT_TOKEN"]
    if not isinstance(header, str) or not hmac.compare_digest(header.encode(), expected.encode()):
        raise PermissionError("Неверный ключ Apple Health")


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("Начало и конец сна должны быть датами ISO 8601 с часовым поясом")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Укажите часовой пояс в датах сна")
    return dt.astimezone(TZ)


def _union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _subtract(intervals, occupied):
    pieces = list(intervals)
    for a, b in occupied:
        result = []
        for start, end in pieces:
            if end <= a or start >= b:
                result.append((start, end))
            else:
                if start < a:
                    result.append((start, a))
                if end > b:
                    result.append((b, end))
        pieces = result
    return pieces


def _minutes(intervals):
    return round(sum((b - a).total_seconds() / 60 for a, b in intervals), 1)


def _export_candidates(value, lower, upper, zone):
    """Resolve yearless local timestamps only when the export/session bounds disambiguate them."""
    if not isinstance(value, str):
        raise ValueError("В экспорте сна отсутствует дата интервала")
    if re.fullmatch(r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
        values = [f"{year}-{value}" for year in range(lower.year - 1, upper.year + 2)]
    else:
        values = [value]
    candidates = set()
    for text in values:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is not None:
            if lower <= dt <= upper:
                candidates.add(dt.astimezone(timezone.utc))
            continue
        for fold in (0, 1):
            local = dt.replace(tzinfo=zone, fold=fold)
            utc = local.astimezone(timezone.utc)
            # Reject nonexistent wall times during DST jumps rather than silently moving them.
            if utc.astimezone(zone).replace(tzinfo=None) == dt and lower <= utc <= upper:
                candidates.add(utc)
    return sorted(candidates)


def normalize_payload(payload):
    """Accept our minimal format or Health Export Kit schema 2; discard all non-sleep fields."""
    if not isinstance(payload, dict):
        raise ValueError("Ожидается JSON-объект с данными сна")
    if "samples" in payload:
        return payload
    meta = payload.get("meta")
    if not isinstance(meta, dict) or meta.get("app") != "Health Export Kit" or type(meta.get("schemaVersion")) is not int or meta["schemaVersion"] != 2:
        raise ValueError("Нужен JSON Health Export Kit версии схемы 2 или объект с samples")
    name = meta.get("timeZone")
    if not isinstance(name, str):
        raise ValueError("В экспорте не указан часовой пояс")
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        # Windows installations may not bundle IANA data; Omsk and UTC have fixed offsets here.
        zone = {"Asia/Omsk": TZ, "UTC": timezone.utc, "Etc/UTC": timezone.utc}.get(name)
        if zone is None:
            raise ValueError("Не удалось прочитать часовой пояс экспорта")
    lower, upper = _instant(meta.get("rangeStart")), _instant(meta.get("rangeEnd"))
    if not timedelta(0) < upper - lower <= timedelta(days=400):
        raise ValueError("Некорректный период экспорта; выберите последние 7 дней")
    lower, upper = lower.astimezone(zone), upper.astimezone(zone)
    section = payload.get("sleep")
    sessions = section.get("sessions") if isinstance(section, dict) else None
    if not isinstance(sessions, list) or not 1 <= len(sessions) <= 800:
        raise ValueError("В файле нет записей сна. Проверьте период и разрешение Health Export Kit на чтение сна")
    samples = []
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError("Некорректная сессия сна")
        pairs = []
        for start in _export_candidates(session.get("start"), lower - timedelta(hours=24), upper, zone):
            for end in _export_candidates(session.get("end"), start, start + timedelta(hours=24), zone):
                if start < end and end > lower:
                    pairs.append((start, end))
        if len(pairs) != 1:
            raise ValueError("Не удалось однозначно определить даты сна. Экспортируйте последние 7 дней")
        start, end = pairs[0]
        stages = session.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError("В сессии нет интервалов фаз сна; нужен JSON с подробностями сна")
        for stage in stages:
            if not isinstance(stage, dict):
                raise ValueError("Некорректная фаза сна")
            starts = _export_candidates(stage.get("start"), start, end, zone)
            ends = _export_candidates(stage.get("end"), start, end, zone)
            if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
                raise ValueError("Интервал фазы не соответствует датам сессии сна")
            samples.append({"start": starts[0].isoformat(), "end": ends[0].isoformat(), "stage": stage.get("stage")})
            if len(samples) > 10000:
                raise ValueError("Слишком много интервалов; экспортируйте последние 7 дней")
    return {"samples": samples}


def import_samples(payload, now=None):
    now = now or datetime.now(TZ)
    payload = normalize_payload(payload)
    samples = payload.get("samples")
    if not isinstance(samples, list) or not 1 <= len(samples) <= 10000:
        raise ValueError("Нужно от 1 до 10000 интервалов сна. Пустой импорт не удаляет историю")
    groups = {}
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Некорректный интервал сна")
        raw = str(sample.get("stage", "")).strip().lower()
        stage = ALIASES.get(raw, raw)
        if stage not in STAGES:
            raise ValueError("Неизвестная фаза сна: используйте core, deep, rem, asleep, awake или in_bed")
        start, end = _instant(sample.get("start")), _instant(sample.get("end"))
        if end <= start or end - start > timedelta(hours=24) or end > now + timedelta(minutes=5) or start < now - timedelta(days=400):
            raise ValueError("Некорректный диапазон сна: максимум 24 часа на интервал, история до 400 дней")
        while start < end:
            night = (start - timedelta(hours=12)).date() + timedelta(days=1)
            boundary = datetime.combine(night, time(12), TZ)
            stop = min(end, boundary)
            groups.setdefault(night.isoformat(), {}).setdefault(stage, []).append((start, stop))
            start = stop
    nights = []
    for day, stages in sorted(groups.items()):
        occupied, values = [], {}
        # Prefer detailed stages to generic asleep samples; duplicate devices never inflate total sleep.
        for stage in ("deep", "rem", "core", "asleep"):
            intervals = _subtract(_union(stages.get(stage, [])), occupied)
            values[stage + "_minutes"] = _minutes(intervals)
            occupied = _union(occupied + intervals)
        values["awake_minutes"] = _minutes(_subtract(_union(stages.get("awake", [])), occupied))
        nights.append({"date": day, "sleep_minutes": _minutes(occupied) if occupied else None,
                       "start": occupied[0][0].isoformat() if occupied else None,
                       "end": occupied[-1][1].isoformat() if occupied else None, **values})
    with _lock:
        doc = _read("apple_sleep", {"nights": []})
        saved = {item["date"]: item for item in doc.get("nights", [])}
        # Each imported sleep day is a complete snapshot; retries replace it rather than adding totals.
        saved.update({item["date"]: item for item in nights})
        doc = {"nights": [saved[key] for key in sorted(saved)[-400:]], "imported_at": now.isoformat()}
        _write("apple_sleep", doc)
    return {"status": "ok", "imported_nights": len(nights), "imported_at": doc["imported_at"]}


def get_summary(start=None, end=None):
    today = datetime.now(TZ).date()
    start, end = start or today - timedelta(days=6), end or today
    with _lock:
        doc = _read("apple_sleep", {"nights": []})
    nights = [n for n in doc.get("nights", []) if start.isoformat() <= n["date"] <= end.isoformat()]
    measured = [n for n in nights if n.get("sleep_minutes") is not None]
    return {"nights": nights, "tracked_nights": len(measured),
            "average_minutes": round(sum(n["sleep_minutes"] for n in measured) / len(measured)) if measured else None,
            "imported_at": doc.get("imported_at"), "timezone": "Asia/Omsk"}


def delete_data():
    with _lock:
        _write("apple_sleep", {"nights": []})


def ai_context(summary):
    if not summary["tracked_nights"]:
        return "Данных сна за выбранный период нет. Не делай выводов о качестве сна."
    import json
    return ("Измерения сна Apple Watch из Apple Health (пользователь разрешил передачу ИИ):\n"
            + json.dumps(summary, ensure_ascii=False)
            + "\nЭто оценки часов, не диагноз. Учитывай длительность, регулярность и полноту данных. "
              "Не считай время в постели сном и отсутствие записи бессонницей. "
              "По одной ночи и процентам фаз не делай категоричных выводов; при необходимости спроси о самочувствии.")
