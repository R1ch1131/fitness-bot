import copy
import types
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
import push_test_queue as queue
from test_push import isolated_function


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.endpoint = 'https://web.push.apple.com/test'
        self.store = {}
        queue._accepted.clear()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(queue, '_read', side_effect=lambda key, default: copy.deepcopy(self.store.get(key, default))))
        self.write = self.stack.enter_context(patch.object(queue, '_write', side_effect=lambda key, value: self.store.update({key: copy.deepcopy(value)})))
        self.subscriptions = self.stack.enter_context(patch('push_service.load_subscriptions', return_value=[{'endpoint': self.endpoint}]))
        self.send = self.stack.enter_context(patch('push_service.send_push_notification', return_value=1))

    def test_35_minutes_survives_memory_reset_and_targets_one_device(self):
        job = queue.schedule_test(self.endpoint, 2100, now=1000)
        self.assertEqual(job['due_at'], 3100)
        queue.dispatch_test_pushes(now=3099)
        self.send.assert_not_called()
        queue._accepted.clear()  # Only persisted state is needed at delivery time.
        queue.dispatch_test_pushes(now=3100)
        self.send.assert_called_once()
        self.assertEqual(self.send.call_args.kwargs['endpoint'], self.endpoint)
        self.assertIn('тест', self.send.call_args.args[0])
        queue.dispatch_test_pushes(now=3120)
        self.assertEqual(self.send.call_count, 1)
        self.assertIsNone(queue.test_status(self.endpoint, now=3120))

    def test_cancel_and_reschedule(self):
        first = queue.schedule_test(self.endpoint, 60, now=1000)
        second = queue.schedule_test(self.endpoint, 2100, now=1001)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(len(self.store['push_test_queue']), 1)
        queue.cancel_test(self.endpoint)
        queue.dispatch_test_pushes(now=3101)
        self.send.assert_not_called()

    def test_failed_delivery_retries_but_unsubscribed_or_expired_does_not_send(self):
        queue.schedule_test(self.endpoint, 60, now=1000)
        self.send.return_value = 0
        queue.dispatch_test_pushes(now=1060)
        self.assertIsNotNone(queue.test_status(self.endpoint, now=1060))
        self.send.return_value = 1
        queue.dispatch_test_pushes(now=1080)
        self.assertEqual(self.send.call_count, 2)
        queue.schedule_test(self.endpoint, 60, now=1100)
        self.subscriptions.return_value = []
        queue.dispatch_test_pushes(now=1160)
        self.assertEqual(self.send.call_count, 2)
        queue.schedule_test(self.endpoint, 60, now=1200)
        self.subscriptions.return_value = [{'endpoint': self.endpoint}]
        queue.dispatch_test_pushes(now=5000)
        self.assertEqual(self.send.call_count, 2)

    def test_queue_write_failure_does_not_claim_success_or_duplicate_accepted_push(self):
        self.write.side_effect = RuntimeError('Storage unavailable')
        with self.assertRaises(RuntimeError):
            queue.schedule_test(self.endpoint, 2100, now=1000)
        self.write.side_effect = lambda key, value: self.store.update({key: copy.deepcopy(value)})
        queue.schedule_test(self.endpoint, 60, now=1000)
        self.write.side_effect = RuntimeError('Storage unavailable')
        with self.assertRaises(RuntimeError):
            queue.dispatch_test_pushes(now=1060)
        with self.assertRaises(RuntimeError):
            queue.dispatch_test_pushes(now=1080)
        self.assertEqual(self.send.call_count, 1)

    def test_api_schedule_does_not_send_immediately_or_change_real_checkin(self):
        class HTTPError(Exception):
            def __init__(self, **kwargs):
                self.status_code = kwargs['status_code']
        namespace = {'Dict': __import__('typing').Dict, 'Any': __import__('typing').Any, 'HTTPException': HTTPError}
        api_test = isolated_function('api.py', 'test_push', namespace)
        response = api_test({'endpoint': self.endpoint, 'delay_seconds': 2100})
        self.assertTrue(response['scheduled'])
        self.send.assert_not_called()
        self.assertEqual(set(self.store), {'push_test_queue'})
        with self.assertRaises(HTTPError) as error:
            api_test({'endpoint': self.endpoint, 'delay_seconds': -1})
        self.assertEqual(error.exception.status_code, 400)

    def test_missing_end_time_never_schedules_a_finished_workout_checkin(self):
        workout = {'id': 'in-progress', 'title': 'Тренировка', 'start_time': '2026-10-26T10:00:00Z'}
        tracker = {'last_known_count': 1, 'last_known_id': 'in-progress'}
        coach = types.SimpleNamespace(hevy=types.SimpleNamespace(api_key='test', get_workouts_count=lambda: 1,
            get_workouts=lambda **kwargs: {'workouts': [workout]}), workouts=[workout],
            analyzer=types.SimpleNamespace(get_latest_workout=lambda: workout))
        save = Mock()
        namespace = {'coach': coach, 'load_workout_tracker': lambda: tracker, 'time': types.SimpleNamespace(time=lambda: 1793016000),
            'save_workout_tracker': Mock(), 'load_pending_checkin': lambda: {}, 'save_pending_checkin': save}
        fn = isolated_function('bot.py', 'check_for_new_workouts_and_sync', namespace)
        fn(Mock())
        save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
