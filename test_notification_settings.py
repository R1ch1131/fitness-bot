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

    def test_weekend_rules_and_five_minute_catch_up(self):
        ns.dispatch_scheduled_push(datetime(2026, 11, 1, 8, 30, tzinfo=ns.TZ))
        self.send.assert_not_called()
        ns.dispatch_scheduled_push(datetime(2026, 11, 1, 12, 3, tzinfo=ns.TZ))
        self.assertEqual(self.send.call_args.kwargs["url"], "/?tab=weekly")
        self.send.reset_mock()
        ns.dispatch_scheduled_push(datetime(2026, 11, 2, 22, 5, tzinfo=ns.TZ))
        self.send.assert_not_called()

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
