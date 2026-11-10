"""One durable evening report per scheduled date, with independent push retries."""
import json
from datetime import datetime
from threading import Lock
from notification_settings import TZ
from cloud_storage import get_cloud_data, set_cloud_data, is_cloud_configured, CloudStorageError
from config import DATA_DIR

LOCK = Lock()
KEY = 'athlete_evening_reports'
FILE = DATA_DIR / 'evening_reports.json'


def _read():
    data = get_cloud_data(KEY, strict=True) if is_cloud_configured() else json.loads(FILE.read_text(encoding='utf-8')) if FILE.exists() else {}
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CloudStorageError('Некорректный журнал отчётов')
    return data


def _write(data):
    data = dict(sorted(data.items())[-40:])
    if is_cloud_configured():
        if not set_cloud_data(KEY, data):
            raise CloudStorageError('Журнал отчётов не сохранён')
    else:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = FILE.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temporary.replace(FILE)


def build_report(due):
    from trainer_runtime import coach, ask_gemini_ai
    from daily_review import collect_daily_review
    context, _ = collect_daily_review(coach, now=due)
    facts = json.loads(context)
    workouts = []
    for workout in coach.workouts:
        end = workout.get('end_time')
        if not end:
            continue
        try:
            instant = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(TZ)
            if instant.date() == due.date():
                report = coach.analyzer.analyze_workout(workout)
                workouts.append({key: report.get(key) for key in ('title', 'duration_minutes', 'total_tonnage_kg', 'total_working_sets')})
        except (ValueError, TypeError):
            continue
    facts['workouts'] = workouts
    try:
        import sleep_data
        summary = sleep_data.get_summary(due.date(), due.date())
        facts['sleep'] = sleep_data.ai_context(summary)
    except Exception:
        facts['sleep_status'] = 'unavailable'
    fallback = [f"🌙 Вечерний итог · {due.strftime('%d.%m.%Y')}"]
    nutrition = facts.get('nutrition')
    if nutrition:
        fallback.append(f"Питание: {nutrition.get('calories', '—')} ккал. Белки: {nutrition.get('protein', '—')} г, жиры: {nutrition.get('fat', '—')} г, углеводы: {nutrition.get('carbs', '—')} г.")
    else:
        fallback.append('Нет подтверждённых записей питания за этот день.')
    if workouts:
        fallback.append('Тренировки: ' + ', '.join(str(workout.get('title') or 'Тренировка') for workout in workouts))
    if facts.get('reading'):
        book = facts['reading']
        fallback.append(f"Чтение: «{book['title']}», {book['current_page']} из {book['total_pages']} стр.")
    fallback.append('Это доступные итоги дня. Подробный разбор ИИ временно недоступен.')
    try:
        reply = ask_gemini_ai(
            'Составь вечернее сообщение пользователю: краткий итог питания с БЖУ и целями, '
            'тренировка, привычки и чтение, если есть данные, затем один спокойный совет на завтра. '
            'До 220 слов. Не выдумывай данные, не называй отсутствие записей нулевыми значениями. '
            'Не утверждай, что мышцы полностью восстановлены или защищены от катаболизма. '
            'Не обещай точный дефицит без данных о расходе энергии. Без спойлеров книг. '
            'Используй только факты этой даты. Начни с даты отчёта.',
            force_llm=True, context_only=True, extra_context=json.dumps(facts, ensure_ascii=False))
        if reply and not reply.startswith('⚠️'):
            return reply
    except Exception as error:
        print(f'[Evening] AI: {type(error).__name__}')
    return '\n\n'.join(fallback)


def dispatch_evening_report(due, *, report_id=None):
    if not LOCK.acquire(blocking=False):
        return False
    try:
        from chat_store import append_message, read_history
        from push_service import send_push_notification
        report_id = report_id or 'evening-' + due.date().isoformat()
        records = _read()
        record = records.get(report_id)
        if not record:
            existing = next((m for m in read_history() if m.get('id') == report_id), None)
            message = existing or {'id': report_id, 'sender': 'coach', 'text': build_report(due),
                                   'timestamp': due.strftime('%d.%m · %H:%M'), 'created_at': due.isoformat()}
            append_message(message)
            record = {'message': message, 'push_sent': False}
            records[report_id] = record
            _write(records)
        if record.get('push_sent'):
            return True
        title = 'Тестовый отчёт готов 🌙' if report_id.startswith('evening-test-') else 'Вечерний отчёт готов 🌙'
        accepted = send_push_notification(title, 'Итоги питания, активности и дня — в чате тренера.',
                                          url='/?tab=chat', tag=report_id)
        if accepted:
            record['push_sent'] = True
            _write(records)
        return bool(accepted)
    finally:
        LOCK.release()


def schedule_test(run_at, review_at):
    """Persist a single test without changing the daily schedule."""
    with LOCK:
        records = _read()
        identifier = 'evening-test-midnight-' + run_at.date().isoformat()
        records[identifier] = {'run_at': run_at.isoformat(), 'review_at': review_at.isoformat(), 'pending': True}
        _write(records)
    return identifier


def dispatch_pending_tests(now=None):
    now = now or datetime.now(TZ)
    with LOCK:
        pending = [(key, value.copy()) for key, value in _read().items() if value.get('pending') and datetime.fromisoformat(value['run_at']) <= now]
    for identifier, record in pending:
        # Remove the queue placeholder: dispatch owns the durable message journal.
        with LOCK:
            records = _read()
            current = records.get(identifier, {})
            if not current.get('pending'):
                continue
            if not current.get('message'):
                from chat_store import append_message, read_history
                due = datetime.fromisoformat(record['review_at'])
                message = next((m for m in read_history() if m.get('id') == identifier), None)
                if not message:
                    message = {'id': identifier, 'sender': 'coach', 'text': build_report(due), 'timestamp': now.strftime('%d.%m · %H:%M'), 'created_at': now.isoformat()}
                    append_message(message)
                current.update(message=message, push_sent=False)
                records[identifier] = current
                _write(records)
        if dispatch_evening_report(datetime.fromisoformat(record['review_at']), report_id=identifier):
            with LOCK:
                records = _read()
                records[identifier]['pending'] = False
                _write(records)
