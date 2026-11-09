import copy
import unittest
from datetime import datetime
from unittest.mock import patch
import chat_store
import evening_report as evening


class EveningTests(unittest.TestCase):
    def test_manual_report_does_not_consume_the_scheduled_report(self):
        records = {}
        due = datetime(2026, 11, 10, 23, 0, tzinfo=evening.TZ)
        with patch.object(evening, '_read', return_value=records), patch.object(evening, '_write'), \
             patch.object(evening, 'build_report', return_value='Итоги') as build, \
             patch('chat_store.read_history', return_value=[]), patch('chat_store.append_message'), \
             patch('push_service.send_push_notification', return_value=1):
            evening.dispatch_evening_report(due, report_id='evening-test-request')
            evening.dispatch_evening_report(due, report_id='evening-test-request')
            evening.dispatch_evening_report(due)
            self.assertEqual(build.call_count, 2)
            self.assertEqual(set(records), {'evening-test-request', 'evening-2026-11-10'})

    def test_stale_phone_does_not_erase_report_but_explicit_clear_can(self):
        stored = []
        def write(messages):
            stored[:] = copy.deepcopy(messages)
        with patch.object(chat_store, 'read_history', side_effect=lambda: copy.deepcopy(stored)), patch.object(chat_store, '_write', side_effect=write):
            chat_store.append_message({'id': 'evening-2026-11-09', 'sender': 'coach', 'text': 'Итоги дня', 'timestamp': '23:00'})
            chat_store.save_history([{'id': '1', 'sender': 'user', 'text': 'Привет', 'timestamp': '22:00'}])
            self.assertEqual(len(stored), 2)
            chat_store.save_history([], clear=True)
            self.assertEqual(stored, [])

    def test_push_retry_does_not_generate_or_append_the_report_twice(self):
        records = {}
        due = datetime(2026, 11, 9, 23, 0, tzinfo=evening.TZ)
        with patch.object(evening, '_read', return_value=records), patch.object(evening, '_write'), \
             patch.object(evening, 'build_report', return_value='Доступные итоги') as build, \
             patch('chat_store.read_history', return_value=[]), patch('chat_store.append_message') as append, \
             patch('push_service.send_push_notification', side_effect=[0, 1]) as push:
            self.assertFalse(evening.dispatch_evening_report(due))
            self.assertTrue(evening.dispatch_evening_report(due))
            self.assertTrue(evening.dispatch_evening_report(due))
            build.assert_called_once()
            append.assert_called_once()
            self.assertEqual(push.call_count, 2)
            self.assertEqual(push.call_args.kwargs['url'], '/?tab=chat')

    def test_no_push_if_chat_storage_failed(self):
        due = datetime(2026, 11, 9, 23, 0, tzinfo=evening.TZ)
        with patch.object(evening, '_read', return_value={}), patch.object(evening, 'build_report', return_value='Итоги'), \
             patch('chat_store.read_history', return_value=[]), patch('chat_store.append_message', side_effect=RuntimeError('offline')), \
             patch('push_service.send_push_notification') as push:
            with self.assertRaises(RuntimeError):
                evening.dispatch_evening_report(due)
            push.assert_not_called()


if __name__ == '__main__':
    unittest.main()
