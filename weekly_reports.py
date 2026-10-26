"""Calendar-week facts and reproducible report images for the PWA."""
import io
import threading
import time
from datetime import date, datetime, timedelta

from notification_settings import TZ

_cache = {}
_lock = threading.Lock()


def week_start(value=None):
    today = datetime.now(TZ).date()
    chosen = date.fromisoformat(value) if value else today
    if chosen > today or chosen < today - timedelta(days=365):
        raise ValueError("Можно выбрать неделю за последний год")
    return chosen - timedelta(days=chosen.weekday())


def summary(coach, start):
    today = datetime.now(TZ).date()
    key = (id(coach), start.isoformat(), today.isoformat())
    with _lock:
        entry = _cache.get(key)
        if entry and time.monotonic() - entry[0] < 300:
            return entry[1]
        result = _collect(coach, start, today)
        _cache.clear()
        _cache[key] = (time.monotonic(), result)
        return result


def clear_cache():
    with _lock:
        _cache.clear()


def _collect(coach, start, today):
    from analyzer import parse_iso
    end = start + timedelta(days=6)
    workouts = {}
    warnings = set()
    for workout in coach.workouts:
        if not workout.get("end_time"):
            continue
        when = parse_iso(workout.get("start_time") or workout["end_time"])
        if when:
            workouts.setdefault(when.astimezone(TZ).date(), []).append(workout)
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        nutrition = {}
        if day <= today and coach.yazio.is_configured():
            try:
                nutrition = coach.yazio.get_daily_summary(day) or {}
            except Exception:
                warnings.add("Часть данных YAZIO временно недоступна")
        logged = nutrition.get("calories", 0) > 0 or nutrition.get("protein", 0) > 0
        sessions = workouts.get(day, []) if day <= today else []
        tonnage = sum(coach.analyzer.analyze_workout(w).get("total_tonnage_kg", 0) for w in sessions)
        days.append({"date": day.isoformat(), "weekday": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][offset],
                     "is_future": day > today, "is_logged": logged,
                     **{k: round(nutrition.get(k, 0), 1) for k in ("calories", "protein", "fat", "carbs")},
                     "workout_count": len(sessions), "workout_titles": [w.get("title", "Тренировка") for w in sessions],
                     "tonnage_kg": round(tonnage)})
    tracked = [d for d in days if d["is_logged"]]
    averages = {k: round(sum(d[k] for d in tracked) / len(tracked), 1) if tracked else None
                for k in ("calories", "protein", "fat", "carbs")}
    averages["tracked_days"] = len(tracked)
    weights = []
    if coach.yazio.is_configured() and coach.yazio.client:
        try:
            from yazio_exporter.export_body import fetch_weight_range
            raw = coach.yazio._execute_with_retry(fetch_weight_range, coach.yazio.client,
                                                  start.isoformat(), (min(end, today) + timedelta(days=1)).isoformat()) or {}
            weights = [(day, value) for day, value in sorted(raw.items())
                       if start.isoformat() <= day <= min(end, today).isoformat() and isinstance(value, (int, float)) and value > 0]
        except Exception:
            warnings.add("История веса временно недоступна")
    return {"period_start": start.isoformat(), "period_end": end.isoformat(), "as_of": datetime.now(TZ).isoformat(),
            "days": days, "averages": averages, "workout_count": sum(d["workout_count"] for d in days),
            "tonnage_kg": sum(d["tonnage_kg"] for d in days),
            "weight_change": round(weights[-1][1] - weights[0][1], 1) if len(weights) >= 2 else None,
            "weight_measurements": len(weights), "warnings": sorted(warnings), "report_markdown": ""}


def render_image(report, sleep=None):
    from PIL import Image, ImageDraw
    from report_image import _get_font
    image = Image.new("RGB", (1080, 1560), "#0b0f19")
    draw = ImageDraw.Draw(image)
    white, muted, green = "#f8fafc", "#94a3b8", "#00d084"

    def text(x, y, value, size=24, fill=white, bold=False):
        draw.text((x, y), str(value), font=_get_font(size, bold), fill=fill)

    def fit(value, width, size=23):
        font = _get_font(size)
        while value and draw.textlength(value, font=font) > width:
            value = value[:-2].rstrip() + "…"
        return value

    def number(value, unit=""):
        return "Нет данных" if value is None else f"{value:,.0f}".replace(",", " ") + unit

    text(52, 44, "FITPULSE  /  HEVY + YAZIO", 22, green, True)
    text(52, 92, "Твоя неделя в цифрах", 54, bold=True)
    start, end = date.fromisoformat(report["period_start"]), date.fromisoformat(report["period_end"])
    text(52, 166, f"{start:%d.%m} — {end:%d.%m.%Y}  ·  по Омску", 25, muted)
    avg = report["averages"]
    delta = report["weight_change"]
    cards = [("ТРЕНИРОВКИ", str(report["workout_count"]), f"Тоннаж: {number(report['tonnage_kg'], ' кг')}", green),
             ("ДИНАМИКА ВЕСА", "Нет данных" if delta is None else f"{delta:+.1f} кг", "По замерам внутри недели", "#a78bfa"),
             ("КАЛОРИИ / ДЕНЬ", number(avg["calories"], " ккал"), f"Записано дней: {avg['tracked_days']} из 7", "#f59e0b"),
             ("БЕЛОК / ДЕНЬ", number(avg["protein"], " г"), "Среднее по записанным дням", "#38bdf8")]
    for idx, (label, value, note, accent) in enumerate(cards):
        x, y = 52 + (idx % 2) * 500, 236 + (idx // 2) * 174
        draw.rounded_rectangle((x, y, x + 476, y + 150), 22, fill="#111726", outline="#273449", width=2)
        draw.rounded_rectangle((x + 20, y + 20, x + 25, y + 130), 2, fill=accent)
        text(x + 42, y + 20, label, 20, muted, True)
        text(x + 42, y + 55, value, 37, accent, True)
        text(x + 42, y + 110, note, 18, muted)
    sleep_text = "Сон Apple Watch · подключается через «Команды»"
    if sleep and sleep["tracked_nights"]:
        minutes = sleep["average_minutes"]
        sleep_text = f"Сон · в среднем {minutes // 60} ч {minutes % 60:02d} мин · ночей с данными: {sleep['tracked_nights']}"
    draw.rounded_rectangle((52, 596, 1028, 665), 18, fill="#182037")
    text(78, 614, sleep_text, 24, "#c4b5fd")
    text(52, 708, "ПО ДНЯМ", 26, bold=True)
    text(235, 711, "ККАЛ", 20, muted, True)
    text(410, 711, "БЕЛОК", 20, muted, True)
    text(585, 711, "ТРЕНИРОВКА", 20, muted, True)
    for idx, day in enumerate(report["days"]):
        y = 760 + idx * 76
        draw.rounded_rectangle((52, y, 1028, y + 64), 14, fill="#111726")
        text(72, y + 15, day["weekday"], 25, green, True)
        text(130, y + 19, day["date"][8:10] + "." + day["date"][5:7], 20, muted)
        text(235, y + 16, number(day["calories"]) if day["is_logged"] else "—", 24)
        text(410, y + 16, number(day["protein"], " г") if day["is_logged"] else "—", 24)
        title = ", ".join(day["workout_titles"]) if day["workout_count"] else ("Впереди" if day["is_future"] else "Нет записи")
        text(585, y + 17, fit(title, 410), 23, "#c4b5fd" if day["workout_count"] else muted)
    text(52, 1340, "Честный отчёт по твоим записям", 28, bold=True)
    text(52, 1391, "Пропуски не считаются нулями. Средние — по дням с питанием.", 22, muted)
    text(52, 1430, "Разбор прогресса и план на следующую неделю — у AI-тренера.", 22, muted)
    text(52, 1501, "FITPULSE", 20, green, True)
    text(730, 1501, "Сформировано " + datetime.fromisoformat(report["as_of"]).strftime("%d.%m %H:%M"), 18, muted)
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
