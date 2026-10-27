"""Selected body-mass fields from authenticated Health Export Kit imports."""
import math
from copy import deepcopy
from datetime import date, timedelta


def normalize_weights(payload, now):
    if not isinstance(payload, dict):
        return []
    body = payload.get('additional', {}).get('body') if isinstance(payload.get('additional'), dict) else None
    if not isinstance(body, dict):
        return []
    rows = body.get('daily', [])
    if not isinstance(rows, list) or len(rows) > 401:
        raise ValueError('Некорректная история веса; выберите последние 7–30 дней')
    selected = [r for r in rows if isinstance(r, dict) and isinstance(r.get('values'), dict) and r['values'].get('bodyMass') is not None]
    if not selected:
        return []
    meta = payload.get('meta', {})
    if not isinstance(meta, dict) or meta.get('app') != 'Health Export Kit' or type(meta.get('schemaVersion')) is not int or meta['schemaVersion'] != 2:
        raise ValueError('Для веса нужен JSON Health Export Kit версии схемы 2')
    from sleep_data import _instant
    lower, upper = _instant(meta.get('rangeStart')), _instant(meta.get('rangeEnd'))
    if not timedelta(0) < upper - lower <= timedelta(days=400):
        raise ValueError('Некорректный период экспорта веса')
    # daily dates belong to the export timezone, not to an invented sample timestamp.
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from notification_settings import TZ
    from datetime import timezone
    name = meta.get('timeZone')
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = {'Asia/Omsk': TZ, 'UTC': timezone.utc, 'Etc/UTC': timezone.utc}.get(name)
        if zone is None:
            raise ValueError('Не удалось прочитать часовой пояс веса')
    units = body.get('units')
    unit = units.get('bodyMass') if isinstance(units, dict) else None
    if unit not in ('kg', 'lb', 'lbs'):
        raise ValueError('Неизвестная единица веса: нужны kg или lb')
    result = {}
    for row in selected:
        try:
            day = date.fromisoformat(row.get('date', ''))
        except (ValueError, TypeError):
            raise ValueError('Некорректная дата взвешивания')
        value = row['values']['bodyMass']
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Вес должен быть конечным числом')
        kg = value if unit == 'kg' else value * 0.45359237
        if not 20 <= kg <= 400:
            raise ValueError('Вес вне допустимого диапазона 20–400 кг')
        if not lower.astimezone(zone).date() <= day <= upper.astimezone(zone).date() or day > now.astimezone(zone).date() or day < now.date() - timedelta(days=400):
            raise ValueError('Дата взвешивания вне периода экспорта')
        if day.isoformat() in result and result[day.isoformat()] != round(kg, 2):
            raise ValueError('Несколько разных дневных значений веса за одну дату')
        result[day.isoformat()] = round(kg, 2)
    return [{'date': day, 'weight': value} for day, value in sorted(result.items())]


def apply_report(report, health):
    """Overlay authorized health records after the shared public YAZIO cache."""
    if not health or not health.get('weight_history'):
        return report
    import weekly_reports
    result = deepcopy(report)
    cutoff = min(date.fromisoformat(report['period_end']), date.fromisoformat(report['as_of'][:10]))
    points = [(w['date'], w['weight']) for w in health['weight_history'] if w['date'] <= cutoff.isoformat()]
    if not points:
        return report
    measured = [(d, w) for d, w in points if d >= report['period_start']]
    result['weight_change'] = round(measured[-1][1] - measured[0][1], 1) if len(measured) >= 2 else None
    result['weight_measurements'] = len(measured)
    result['weight_source'] = 'apple_health'
    result['goal_forecast'] = weekly_reports.goal_forecast(points, cutoff)
    result['goal_forecast']['source'] = 'apple_health'
    result['warnings'] = [w for w in result.get('warnings', []) if w != 'История веса временно недоступна']
    return result


def widget_snapshot(today=None):
    """Small local/cloud snapshot. Never calls Hevy, Gemini or YAZIO."""
    from datetime import datetime
    from notification_settings import TZ, _read
    from weekly_reports import goal_forecast
    today = today or datetime.now(TZ).date()
    doc = _read('apple_sleep', {'weights': []})
    forecast = goal_forecast([(w.get('date'), w.get('weight')) for w in doc.get('weights', []) if isinstance(w, dict)], today)
    return {'status': 'ok' if forecast['current_weight'] is not None else 'empty',
            'source': 'apple_health', 'measured_on': forecast['measured_on'],
            **{k: forecast[k] for k in ('start_weight', 'current_weight', 'goal_weight', 'lost_kg', 'remaining_kg', 'progress_percent')},
            'as_of': datetime.now(TZ).isoformat()}
