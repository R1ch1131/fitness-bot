"""Web-only startup. Background work never waits before binding the HTTP port."""
import os
import threading
import time

_started = False
_task_lock = threading.Lock()
_sync_ready = threading.Event()

def authorize_scheduler(header):
    import hashlib, hmac
    secret = os.getenv('HEALTH_IMPORT_TOKEN', '')
    if len(secret) < 32 or not isinstance(header, str):
        return False
    expected = hashlib.sha256(('fitpulse-scheduler-v1\0' + secret).encode()).hexdigest()
    return hmac.compare_digest(header, 'Bearer ' + expected)



def _run_pending_tasks():
    from notification_settings import dispatch_scheduled_push
    from custom_reminders import dispatch_custom_pushes
    from push_test_queue import dispatch_test_pushes
    from trainer_runtime import dispatch_checkin_if_due
    errors = []
    for task in (dispatch_scheduled_push, dispatch_custom_pushes, dispatch_test_pushes, dispatch_checkin_if_due):
        try:
            task()
        except Exception as error:
            print(f'[Scheduler] {task.__name__}: {type(error).__name__}')
            errors.append(task.__name__)
    if errors:
        raise RuntimeError('Scheduled tasks failed: ' + ', '.join(errors))


def run_pending_tasks():
    if not _sync_ready.is_set():
        return 'busy'
    if not _task_lock.acquire(blocking=False):
        return 'busy'
    try:
        _run_pending_tasks()
        return 'ok'
    finally:
        _task_lock.release()


def start_background_services():
    global _started
    if _started:
        return
    _started = True
    def sync():
        from trainer_runtime import coach, check_for_new_workouts_and_sync
        try:
            coach.reload(auto_sync=True)
        except Exception as error:
            print(f'[Startup] Sync: {type(error).__name__}')
        finally:
            _sync_ready.set()
        while True:
            try:
                check_for_new_workouts_and_sync()
            except Exception as error:
                print(f'[Hevy] Sync: {type(error).__name__}')
            time.sleep(90)
    def scheduled():
        while True:
            try:
                run_pending_tasks()
            except Exception as error:
                print(f'[Scheduler] Retry on next tick: {type(error).__name__}')
            time.sleep(20)
    threading.Thread(target=sync, daemon=True, name='hevy-sync').start()
    threading.Thread(target=scheduled, daemon=True, name='app-scheduler').start()


def run():
    import uvicorn
    uvicorn.run('api:app', host='0.0.0.0', port=int(os.getenv('PORT', '8080')))
