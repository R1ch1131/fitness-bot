import copy
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import custom_reminders as cr


class CustomReminderTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.now = datetime(2026, 10, 26, 10, 0, tzinfo=cr.TZ)
        self.value = {"title": "Вода", "body": "Выпей стакан воды", "time": "11:00", "weekdays": [0, 2, 4], "enabled": True}
        cr._accepted.clear()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(cr, '_read', side_effect=lambda key, default: copy.deepcopy(self.store.get(key, default))))
        self.write = stack.enter_context(patch.object(cr, '_write', side_effect=lambda key, value: self.store.update({key: copy.deepcopy(value)})))
        self.send = stack.enter_context(patch('push_service.send_push_notification', return_value=1))

    def test_create_edit_disable_delete_and_persisted_next_run(self):
        item = cr.create_reminder(self.value, self.now)
        self.assertTrue(item['id'])
        loaded = cr.list_reminders(self.now)
        self.assertEqual(loaded[0]['next_run'], '2026-10-26T11:00:00+06:00')
        updated = cr.update_reminder(item['id'], {**self.value, 'title': 'Вода и отдых', 'time': '12:00'})
        self.assertEqual(updated['created_at'], item['created_at'])
        self.assertEqual(cr.list_reminders(self.now)[0]['title'], 'Вода и отдых')
        cr.update_reminder(item['id'], {**self.value, 'enabled': False})
        self.assertIsNone(cr.list_reminders(self.now)[0]['next_run'])
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1))
        self.send.assert_not_called()
        cr.delete_reminder(item['id'])
        self.assertEqual(cr.list_reminders(self.now), [])
        with self.assertRaises(KeyError):
            cr.delete_reminder(item['id'])

    def test_validated_fields(self):
        for field, value in [('title', ''), ('title', 'a' * 81), ('body', 'a' * 241), ('time', '24:00'),
                             ('weekdays', []), ('weekdays', [0, 0]), ('weekdays', [True]), ('weekdays', [7]), ('enabled', 1)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                cr.create_reminder({**self.value, field: value}, self.now)
        with self.assertRaises(ValueError):
            cr.create_reminder({**self.value, 'id': 'tampered'}, self.now)

    def test_delivery_uses_text_weekday_timezone_and_survives_restart(self):
        item = cr.create_reminder(self.value, self.now)
        cr.dispatch_custom_pushes(self.now + timedelta(minutes=59))
        self.send.assert_not_called()
        cr.dispatch_custom_pushes(datetime(2026, 10, 26, 5, 0, tzinfo=timezone.utc))
        self.send.assert_called_once_with('Вода', 'Выпей стакан воды', url='/', tag='custom-' + item['id'])
        cr._accepted.clear()
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1, seconds=20))
        self.send.assert_called_once()
        self.assertEqual(cr.list_reminders(self.now + timedelta(hours=1))[0]['next_run'], '2026-10-28T11:00:00+06:00')

    def test_new_reminder_does_not_fire_retroactively(self):
        cr.create_reminder({**self.value, 'time': '09:30'}, self.now)
        cr.dispatch_custom_pushes(self.now)
        self.send.assert_not_called()
        self.assertEqual(cr.list_reminders(self.now)[0]['next_run'], '2026-10-28T09:30:00+06:00')

    def test_late_friday_delivery_after_midnight_and_removed_reminder(self):
        item = cr.create_reminder({**self.value, 'time': '23:55', 'weekdays': [4]}, self.now)
        cr.dispatch_custom_pushes(datetime(2026, 10, 31, 0, 10, tzinfo=cr.TZ))
        self.send.assert_called_once()
        cr.delete_reminder(item['id'])
        cr.dispatch_custom_pushes(datetime(2026, 11, 6, 23, 55, tzinfo=cr.TZ))
        self.send.assert_called_once()

    def test_changed_time_and_provider_retry(self):
        item = cr.create_reminder(self.value, self.now)
        self.send.return_value = 0
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1))
        self.send.return_value = 1
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1, minutes=10))
        self.assertEqual(self.send.call_count, 2)
        cr.update_reminder(item['id'], {**self.value, 'time': '11:30'})
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1, minutes=30))
        self.assertEqual(self.send.call_count, 3)
        cr.update_reminder(item['id'], self.value)
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1, minutes=31))
        self.assertEqual(self.send.call_count, 3)

    def test_save_failure_is_visible_and_accepted_push_is_not_repeated(self):
        self.write.side_effect = RuntimeError('Cloud down')
        with self.assertRaises(RuntimeError):
            cr.create_reminder(self.value, self.now)
        self.assertEqual(cr.list_reminders(self.now), [])
        self.write.side_effect = lambda key, value: self.store.update({key: copy.deepcopy(value)})
        cr.create_reminder(self.value, self.now)
        self.write.side_effect = RuntimeError('Cloud down')
        with self.assertRaises(RuntimeError):
            cr.dispatch_custom_pushes(self.now + timedelta(hours=1))
        with self.assertRaises(RuntimeError):
            cr.dispatch_custom_pushes(self.now + timedelta(hours=1, seconds=20))
        self.send.assert_called_once()
        self.write.side_effect = lambda key, value: self.store.update({key: copy.deepcopy(value)})
        cr.dispatch_custom_pushes(self.now + timedelta(hours=1, seconds=40))
        self.send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
