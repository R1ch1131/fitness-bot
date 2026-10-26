"""Durable device-specific push tests; no browser timers or workout mutations."""
import time
import uuid
from notification_settings import _read, _write, _lock

ALLOWED_DELAYS = {60, 35 * 60}
_accepted = set()


def schedule_test(endpoint, delay_seconds, now=None):
    if type(delay_seconds) is not int or delay_seconds not in ALLOWED_DELAYS:
        raise ValueError("Выберите тест через 1 или 35 минут")
    now = time.time() if now is None else now
    job = {"id": uuid.uuid4().hex, "due_at": now + delay_seconds,
           "expires_at": now + delay_seconds + 3600}
    with _lock:
        queue = _read("push_test_queue", {})
        queue = {key: value for key, value in queue.items() if value.get("expires_at", 0) > now}
        queue[endpoint] = job  # One pending test per device; repeat scheduling replaces it.
        _write("push_test_queue", queue)
    return job


def cancel_test(endpoint):
    with _lock:
        queue = _read("push_test_queue", {})
        queue.pop(endpoint, None)
        _write("push_test_queue", queue)


def test_status(endpoint, now=None):
    now = time.time() if now is None else now
    with _lock:
        job = _read("push_test_queue", {}).get(endpoint)
    if not job or job.get("expires_at", 0) <= now or job.get("id") in _accepted:
        return None
    return {"due_at": job["due_at"]}


def dispatch_test_pushes(now=None):
    from push_service import load_subscriptions, send_push_notification
    now = time.time() if now is None else now
    with _lock:
        jobs = _read("push_test_queue", {})
    due_jobs = {endpoint: job for endpoint, job in jobs.items() if job.get("due_at", float("inf")) <= now}
    if not due_jobs:
        return
    endpoints = {sub.get("endpoint") for sub in load_subscriptions()}
    for endpoint, job in due_jobs.items():
        done = job.get("expires_at", 0) <= now or endpoint not in endpoints or job["id"] in _accepted
        if not done:
            done = bool(send_push_notification(
                "FitPulse: фоновый тест уведомлений",
                "Это тест, запланированный на сервере. Проверь, пришло ли уведомление при закрытом приложении.",
                url="/", endpoint=endpoint, tag="background-test-" + job["id"],
            ))
            if done:
                _accepted.add(job["id"])
        if done:
            with _lock:
                queue = _read("push_test_queue", {})
                # A newer test may have replaced this job during network delivery.
                if queue.get(endpoint, {}).get("id") == job["id"]:
                    queue.pop(endpoint)
                    _write("push_test_queue", queue)
            _accepted.discard(job["id"])
