"""Calendar-week facts and reproducible report images for the PWA."""
import io
import math
import hashlib
import threading
import time
from datetime import date, datetime, timedelta

from notification_settings import TZ

_cache = {}
_lock = threading.Lock()
_analysis_cache = {}
_analysis_lock = threading.Lock()


def cached_analysis(context, question):
    key = hashlib.sha256((question + "\n" + context).encode()).hexdigest()
    with _analysis_lock:
        entry = _analysis_cache.get(key)
        if entry and time.monotonic() - entry[0] < 600:
            return entry[1]
    return None


def remember_analysis(context, question, reply):
    key = hashlib.sha256((question + "\n" + context).encode()).hexdigest()
    with _analysis_lock:
        if len(_analysis_cache) >= 32:
            del _analysis_cache[next(iter(_analysis_cache))]
        _analysis_cache[key] = (time.monotonic(), reply)


def sleep_workout_context(coach, start):
    """Use already loaded Hevy records; never fetch YAZIO for a sleep question."""
    from analyzer import parse_iso
    end = start + timedelta(days=6)
    sessions = []
    for workout in coach.workouts:
        when = parse_iso(workout.get("end_time"))
        if when and start <= when.astimezone(TZ).date() <= end:
            sessions.append({"title": workout.get("title"), "start": workout.get("start_time"), "end": workout["end_time"]})
    return {"period_start": start.isoformat(), "period_end": end.isoformat(), "workouts": sessions}


def week_start(value=None):
    today = datetime.now(TZ).date()
    chosen = date.fromisoformat(value) if value else today
    if chosen > today or chosen < today - timedelta(days=365):
        raise ValueError("Можно выбрать неделю за последний год")
    return chosen - timedelta(days=chosen.weekday())


def summary(coach, start, include_weights=True):
    today = datetime.now(TZ).date()
    key = (id(coach), start.isoformat(), today.isoformat(), include_weights)
    with _lock:
        entry = _cache.get(key)
        if entry and time.monotonic() - entry[0] < 300:
            return entry[1]
        result = _collect(coach, start, today, include_weights=include_weights)
        _cache.clear()
        _cache[key] = (time.monotonic(), result)
        return result


def clear_cache():
    with _lock:
        _cache.clear()


def goal_forecast(weights, as_of, start_weight=103.0, goal_weight=80.0):
    """Project from measured weights only; historical weeks never use later records."""
    samples = []
    for day, value in weights:
        try:
            measured = date.fromisoformat(day)
            if type(value) in (int, float) and math.isfinite(value) and 20 <= value <= 400 and measured <= as_of:
                samples.append((measured, float(value)))
        except (ValueError, TypeError):
            continue
    samples = sorted(dict(samples).items())
    current = samples[-1][1] if samples else None
    measured_on = samples[-1][0] if samples else None
    recent = [(day, value) for day, value in samples if day >= as_of - timedelta(days=28)]
    span = (recent[-1][0] - recent[0][0]).days if len(recent) >= 2 else 0
    rate = None
    if span >= 7:
        xs = [(d - recent[0][0]).days for d, _ in recent]
        ys = [v for _, v in recent]
        xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
        slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / sum((x - xm) ** 2 for x in xs)
        rate = -slope * 7
    status = 'insufficient'
    if current is not None and current <= goal_weight:
        status = 'reached'
    elif measured_on and (as_of - measured_on).days > 7:
        status = 'stale'
    elif rate is not None:
        status = 'projected' if rate >= 0.05 else 'not_losing'
    milestones = []
    for target in (95.0, 90.0, 85.0, goal_weight):
        reached = current is not None and current <= target
        weeks = (current - target) / rate if status == 'projected' and not reached else None
        # Very distant extrapolations are not useful as calendar promises.
        eta = measured_on + timedelta(days=round(weeks * 7)) if weeks is not None and weeks <= 260 else None
        milestones.append({'weight': target, 'reached': reached, 'eta': eta.isoformat() if eta else None,
                           'weeks': round(weeks, 1) if eta else None})
    return {'as_of': as_of.isoformat(), 'measured_on': measured_on.isoformat() if measured_on else None,
            'start_weight': start_weight, 'current_weight': current, 'goal_weight': goal_weight,
            'lost_kg': round(max(0, start_weight - current), 1) if current is not None else None,
            'remaining_kg': round(max(0, current - goal_weight), 1) if current is not None else None,
            'progress_percent': round(max(0, min(100, (start_weight - current) / (start_weight - goal_weight) * 100)), 1) if current is not None else None,
            'rate_kg_week': round(rate, 2) if rate is not None else None, 'status': status,
            'sample_count': len(recent), 'span_days': span, 'milestones': milestones}


def _collect(coach, start, today, include_weights=True):
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
    if include_weights and coach.yazio.is_configured() and coach.yazio.client:
        try:
            from yazio_exporter.export_body import fetch_weight_range
            raw = coach.yazio._execute_with_retry(fetch_weight_range, coach.yazio.client,
                                                  (min(end, today) - timedelta(days=28)).isoformat(), (min(end, today) + timedelta(days=1)).isoformat()) or {}
            weights = [(day, value) for day, value in sorted(raw.items())
                       if (min(end, today) - timedelta(days=28)).isoformat() <= day <= min(end, today).isoformat() and type(value) in (int, float) and math.isfinite(value) and 20 <= value <= 400]
        except Exception:
            warnings.add("История веса временно недоступна")
    week_weights = [(day, value) for day, value in weights if day >= start.isoformat()]
    return {"period_start": start.isoformat(), "period_end": end.isoformat(), "as_of": datetime.now(TZ).isoformat(),
            "days": days, "averages": averages, "workout_count": sum(d["workout_count"] for d in days),
            "tonnage_kg": sum(d["tonnage_kg"] for d in days),
            "weight_change": round(week_weights[-1][1] - week_weights[0][1], 1) if len(week_weights) >= 2 else None,
            "goal_forecast": goal_forecast(weights, min(end, today)),
            "weight_measurements": len(week_weights), "warnings": sorted(warnings), "report_markdown": ""}


def render_image(report, sleep=None):
    from PIL import Image, ImageDraw
    from report_image import _get_font
    image = Image.new("RGB", (1080, 1560), "#0b0f19")
    draw = ImageDraw.Draw(image)
    white, muted, green = "#f8fafc", "#94a3b8", "#00d084"

    def text(x, y, value, size=24, fill=white, bold=False):
        draw.text((x, y), str(value), font=_get_font(size, bold), fill=fill)

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
             ("БЕЛОК / ДЕНЬ", number(avg["protein"], " г"), f"Ж {number(avg['fat'], ' г')}  /  У {number(avg['carbs'], ' г')}", "#38bdf8")]
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
    # One row per day, with equally readable values in seven distinct columns.
    columns = [(98, "ДЕНЬ"), (194, "ДАТА"), (326, "ККАЛ"), (460, "БЕЛКИ"),
               (590, "ЖИРЫ"), (734, "УГЛЕВОДЫ"), (932, "ТОННАЖ")]

    def centered(x, y, value, size=28, fill=white, bold=False):
        font = _get_font(size, bold)
        draw.text((x - draw.textlength(str(value), font=font) / 2, y), str(value), font=font, fill=fill)

    for x, label in columns:
        centered(x, 710, label, 21, muted, True)
    for idx, day in enumerate(report["days"]):
        y = 750 + idx * 78
        draw.rounded_rectangle((52, y, 1028, y + 70), 14, fill="#111726")
        centered(columns[0][0], y + 19, day['weekday'], 28, green, True)
        centered(columns[1][0], y + 21, day['date'][8:10] + '.' + day['date'][5:7], 26, muted)
        for index, key in enumerate(('calories', 'protein', 'fat', 'carbs'), start=2):
            value = number(day[key], '' if key == 'calories' else ' г') if day['is_logged'] else '—'
            centered(columns[index][0], y + 19, value, 28, white if day['is_logged'] else muted)
        tonnage = number(day['tonnage_kg'], ' кг') if day['workout_count'] else '—'
        centered(columns[6][0], y + 19, tonnage, 28, '#c4b5fd' if day['workout_count'] else muted)
    text(52, 1340, "Честный отчёт по твоим записям", 28, bold=True)
    text(52, 1391, "Пропуски не считаются нулями. Средние — по дням с питанием.", 22, muted)
    text(52, 1430, "Разбор прогресса и план на следующую неделю — у AI-тренера.", 22, muted)
    text(52, 1501, "FITPULSE", 20, green, True)
    text(730, 1501, "Сформировано " + datetime.fromisoformat(report["as_of"]).strftime("%d.%m %H:%M"), 18, muted)
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
