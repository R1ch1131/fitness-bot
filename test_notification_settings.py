import copy
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import notification_settings as ns
from test_push import isolated_function


class SettingsTests(unittest.TestCase):
    def test_reject_invalid_time_delay_boolean_and_unknown_fields(self):
        for kind, field, value in [("gym", "time", "25:00"), ("laundry", "time", "8:05"),
                                   ("checkin", "delay_minutes", 0), ("checkin", "delay_minutes", 121),
                                   ("checkin", "delay_minutes", True), ("gym", "enabled", "yes")]:
            settings = copy.deepcopy(ns.DEFAULTS)
            settings[kind][field] = value
            with self.assertRaises(ValueError):
                ns.validate_settings(settings)
        with self.assertRaises(ValueError):
            ns.validate_settings({})

    def test_settings_survive_reload_and_failed_cloud_save_is_visible(self):
        with tempfile.TemporaryDirectory(dir=ns.DATA_DIR) as tmp, patch.object(ns, "DATA_DIR", Path(tmp)), patch("cloud_storage.is_cloud_configured", return_value=False):
            value = copy.deepcopy(ns.DEFAULTS)
            value["gym"]["time"] = "07:45"
            value["laundry"]["enabled"] = False
            ns.save_settings(value)
            self.assertEqual(ns.get_settings(), value)
            with patch("cloud_storage.is_cloud_configured", return_value=True), patch("cloud_storage.set_cloud_data", return_value=False):
                with self.assertRaises(RuntimeError):
                    ns.save_settings(ns.DEFAULTS)
            self.assertEqual(ns.get_settings(), value)


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.settings = copy.deepcopy(ns.DEFAULTS)
        self.store = {}
        ns._delivery_memory = None
        ns._delivery_dirty = False
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(ns, "get_settings", return_value=self.settings))
        self.stack.enter_context(patch.object(ns, "_read", side_effect=lambda name, default: copy.deepcopy(self.store.get(name, default))))
        self.write = self.stack.enter_context(patch.object(ns, "_write", side_effect=lambda name, value: self.store.update({name: copy.deepcopy(value)})))
        self.send = self.stack.enter_context(patch("push_service.send_push_notification", return_value=1))

    def test_custom_time_disabled_types_and_restart_deduplication(self):
        self.settings["gym"]["time"] = "07:45"
        now = datetime(2026, 10, 26, 7, 45, 20, tzinfo=ns.TZ)
        ns.dispatch_scheduled_push(now - timedelta(minutes=1))
        self.send.assert_not_called()
        ns.dispatch_scheduled_push(now)
        ns.dispatch_scheduled_push(now + timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 1)
        ns._delivery_memory = None  # Simulate a new server process reading persisted delivery state.
        ns.dispatch_scheduled_push(now + timedelta(seconds=40))
        self.assertEqual(self.send.call_count, 1)
        self.settings["gym"]["enabled"] = False
        ns.dispatch_scheduled_push(now + timedelta(days=1))
        self.assertEqual(self.send.call_count, 1)

    def test_weekend_rules_and_one_hour_catch_up(self):
        ns.dispatch_scheduled_push(datetime(2026, 11, 1, 8, 30, tzinfo=ns.TZ))
        self.send.assert_not_called()
        ns.dispatch_scheduled_push(datetime(2026, 11, 1, 12, 3, tzinfo=ns.TZ))
        self.assertEqual(self.send.call_args.kwargs["url"], "/?tab=weekly")
        self.send.reset_mock()
        self.settings["nutrition"]["enabled"] = False
        ns.dispatch_scheduled_push(datetime(2026, 11, 2, 23, 0, tzinfo=ns.TZ))
        self.send.assert_not_called()

    def test_changed_time_can_send_again_same_day_without_repeating_old_occurrence(self):
        first = datetime(2026, 10, 26, 8, 30, tzinfo=ns.TZ)
        ns.dispatch_scheduled_push(first)
        self.assertEqual(self.send.call_count, 1)
        self.settings["gym"]["time"] = "09:00"
        ns.dispatch_scheduled_push(first + timedelta(minutes=30))
        self.assertEqual(self.send.call_count, 2)
        self.settings["gym"]["time"] = "08:30"
        ns.dispatch_scheduled_push(first + timedelta(minutes=31))
        self.assertEqual(self.send.call_count, 2)

    def test_retry_after_ten_minutes_and_midnight_recovery(self):
        now = datetime(2026, 10, 26, 22, 0, tzinfo=ns.TZ)
        self.send.return_value = 0
        ns.dispatch_scheduled_push(now)
        self.send.return_value = 1
        ns.dispatch_scheduled_push(now + timedelta(minutes=10))
        self.assertEqual(self.send.call_count, 2)
        self.settings["gym"]["time"] = "23:55"
        ns.dispatch_scheduled_push(datetime(2026, 10, 31, 0, 5, tzinfo=ns.TZ))
        self.assertEqual(self.send.call_count, 3)
        self.assertEqual(self.send.call_args.kwargs['url'], '/?tab=workouts')

    def test_legacy_delivery_is_bound_to_old_time_before_saving_new_time(self):
        self.store["notification_delivery"] = {"gym": "2026-10-26"}
        first = datetime(2026, 10, 26, 8, 30, tzinfo=ns.TZ)
        ns.dispatch_scheduled_push(first)
        self.send.assert_not_called()
        self.settings["gym"]["time"] = "09:00"
        ns.dispatch_scheduled_push(first + timedelta(minutes=30))
        self.send.assert_called_once()
        ns._delivery_memory = None
        ns.dispatch_scheduled_push(first + timedelta(minutes=30, seconds=20))
        self.send.assert_called_once()

    def test_storage_failure_retries_journal_without_resending_push(self):
        now = datetime(2026, 10, 26, 22, 0, tzinfo=ns.TZ)
        self.write.side_effect = RuntimeError('Storage down')
        with self.assertRaises(RuntimeError):
            ns.dispatch_scheduled_push(now)
        self.send.assert_called_once()
        self.write.side_effect = lambda key, value: self.store.update({key: copy.deepcopy(value)})
        ns.dispatch_scheduled_push(now + timedelta(seconds=20))
        self.send.assert_called_once()
        self.assertFalse(ns._delivery_dirty)

    def test_next_run_distinguishes_one_am_from_one_pm(self):
        now = datetime(2026, 10, 26, 12, 0, tzinfo=ns.TZ)
        self.settings["gym"]["time"] = "01:00"
        next_run = ns.schedule_status(self.settings, now)["items"]["gym"]["next_run"]
        self.assertEqual(next_run, '2026-10-27T01:00:00+06:00')
        self.settings["gym"]["time"] = "13:00"
        status = ns.schedule_status(self.settings, now)
        self.assertEqual(status["items"]["gym"]["next_run"], '2026-10-26T13:00:00+06:00')
        self.assertNotIn('endpoint', str(status))

    def test_provider_failure_retries_without_marking_sent(self):
        self.send.return_value = 0
        now = datetime(2026, 10, 26, 22, 0, tzinfo=ns.TZ)
        ns.dispatch_scheduled_push(now)
        self.write.assert_not_called()
        self.send.return_value = 1
        ns.dispatch_scheduled_push(now + timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 2)
        self.write.assert_called_once()

    def test_checkin_delay_before_and_after_telegram_time(self):
        end = datetime(2026, 10, 26, 10, 0, tzinfo=ns.TZ)
        pending = {"end_time": end.isoformat(), "due_time": end.timestamp() + 1200, "workout_id": "1"}
        self.settings["checkin"]["delay_minutes"] = 5
        self.assertEqual(ns.dispatch_workout_push(pending, end.timestamp() + 299), 0)
        self.assertEqual(ns.dispatch_workout_push(pending, end.timestamp() + 300), 1)
        self.assertIn("5 мин.", self.send.call_args.args[1])
        self.settings["checkin"]["delay_minutes"] = 60
        self.assertEqual(ns.dispatch_workout_push(pending, end.timestamp() + 1200), 0)
        self.assertEqual(ns.dispatch_workout_push(pending, end.timestamp() + 3600), 1)
        self.settings["checkin"]["enabled"] = False
        self.assertEqual(ns.dispatch_workout_push(pending, end.timestamp() + 3600), 0)
        self.settings["checkin"]["enabled"] = True
        self.assertEqual(ns.dispatch_workout_push(dict(pending, responded=True), end.timestamp() + 3600), 0)
        self.assertEqual(ns.dispatch_workout_push(dict(pending, push_sent=True), end.timestamp() + 3600), 0)

    def test_telegram_stays_at_twenty_minutes_when_app_delay_is_five(self):
        self.settings["checkin"]["delay_minutes"] = 5
        end = datetime(2026, 10, 26, 10, 0, tzinfo=ns.TZ)
        pending = {"end_time": end.isoformat(), "due_time": end.timestamp() + 1200, "workout_id": "1"}
        clock = types.SimpleNamespace(time=lambda: end.timestamp() + 300)
        bot = Mock()
        namespace = {"Optional": __import__("typing").Optional, "time": clock,
                     "load_pending_checkin": lambda: pending, "save_pending_checkin": Mock(),
                     "get_all_subscribers": lambda: [123], "coach": types.SimpleNamespace(workouts=[])}
        dispatch = isolated_function("bot.py", "dispatch_checkin_if_due", namespace)
        dispatch(bot)
        self.send.assert_called_once()
        bot.send_message.assert_not_called()
        clock.time = lambda: end.timestamp() + 1200
        dispatch(bot)
        bot.send_message.assert_called_once()
        self.assertEqual(self.send.call_count, 1)

    def test_in_app_checkin_banner_uses_same_delay_and_toggle(self):
        self.settings["checkin"]["delay_minutes"] = 45
        end = datetime(2026, 10, 26, 10, 0, tzinfo=ns.TZ)
        pending = {"end_time": end.isoformat(), "due_time": end.timestamp() + 1200, "workout_id": "1"}
        clock = types.SimpleNamespace(time=lambda: end.timestamp() + 1200)
        fake_bot = types.ModuleType("bot")
        fake_bot.load_pending_checkin = lambda: pending
        fn = isolated_function("api.py", "get_checkin_notification", {"time": clock})
        with patch.dict("sys.modules", {"bot": fake_bot}):
            self.assertFalse(fn()["should_notify"])
            clock.time = lambda: end.timestamp() + 2700
            self.assertTrue(fn()["should_notify"])
            self.assertIn("45 мин.", fn()["notification"]["body"])
            self.settings["checkin"]["enabled"] = False
            self.assertFalse(fn()["should_notify"])


if __name__ == "__main__":
    unittest.main()
