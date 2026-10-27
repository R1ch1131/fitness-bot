"""Synthetic imports only; no personal exports or live health services."""
import copy
import json
import unittest
from datetime import date, datetime
from unittest.mock import patch, Mock
import types

import sleep_data as sleep
import health_weights as weight
import weekly_reports as weekly
from notification_settings import TZ
from test_sleep_weekly import fake_coach
import test_sleep_weekly as fixtures
from test_push import isolated_function


class HealthWeightTests(unittest.TestCase):
    def setUp(self):
        self.doc = {'nights': []}
        self.now = datetime(2026, 10, 26, 22, tzinfo=TZ)
        self.read = patch.object(sleep, '_read', side_effect=lambda *a: copy.deepcopy(self.doc))
        self.write = patch.object(sleep, '_write', side_effect=lambda name, doc: self.doc.update(copy.deepcopy(doc)))
        self.read.start(); self.write.start()
        self.addCleanup(self.read.stop); self.addCleanup(self.write.stop)

    def export(self):
        value = fixtures.SleepTests().kit_export()
        value['additional']['body'] = {'units': {'bodyMass': 'kg'}, 'daily': [
            {'date': '2026-10-19', 'values': {'bodyMass': 96.0, 'bodyFat': 25, 'leanMass': 70}},
            {'date': '2026-10-26', 'values': {'bodyMass': 95.0, 'bodyFat': 24}},
        ]}
        return value

    def test_combined_import_is_idempotent_and_drops_other_body_fields(self):
        result = sleep.import_samples(self.export(), self.now)
        self.assertEqual((result['imported_nights'], result['imported_weights']), (1, 2))
        self.assertEqual(self.doc['weights'], [{'date': '2026-10-19', 'weight': 96}, {'date': '2026-10-26', 'weight': 95}])
        self.assertNotIn('bodyFat', json.dumps(self.doc))
        self.assertNotIn('medications', json.dumps(self.doc))
        before = copy.deepcopy(self.doc)
        sleep.import_samples(self.export(), self.now)
        self.assertEqual(self.doc, before)
        updated = self.export()
        updated['additional']['body']['daily'][1]['values']['bodyMass'] = 94.9
        sleep.import_samples(updated, self.now)
        self.assertEqual(len(self.doc['weights']), 2)
        self.assertEqual(self.doc['weights'][-1]['weight'], 94.9)

    def test_weight_only_and_sleep_only_preserve_other_history(self):
        original = self.export()
        sleep.import_samples(original, self.now)
        nights = copy.deepcopy(self.doc['nights'])
        original['sleep']['sessions'] = []
        self.assertEqual(sleep.import_samples(original, self.now)['imported_nights'], 0)
        self.assertEqual(self.doc['nights'], nights)
        sleep.import_samples(fixtures.SleepTests().kit_export(), self.now)
        self.assertEqual(len(self.doc['weights']), 2)
        sleep.delete_data()
        self.assertEqual(self.doc['nights'], [])
        self.assertEqual(len(self.doc['weights']), 2)

    def test_bad_weight_rejects_whole_import_before_saving_sleep(self):
        for bad in [float('nan'), float('inf'), True, '95', -1, 500]:
            with self.subTest(bad=bad):
                payload = self.export()
                payload['additional']['body']['daily'][0]['values']['bodyMass'] = bad
                with self.assertRaises(ValueError):
                    sleep.import_samples(payload, self.now)
                self.assertEqual(self.doc, {'nights': []})
        payload = self.export()
        payload['sleep']['sessions'][0]['stages'][0]['stage'] = 'unknown'
        with self.assertRaises(ValueError):
            sleep.import_samples(payload, self.now)
        self.assertEqual(self.doc, {'nights': []})

    def test_rejects_future_out_of_range_and_unknown_units(self):
        for day in ['2026-10-27', '2026-10-01', 'not-a-date']:
            payload = self.export()
            payload['additional']['body']['daily'][0]['date'] = day
            with self.assertRaises(ValueError):
                sleep.import_samples(payload, self.now)
        payload = self.export()
        payload['additional']['body']['units']['bodyMass'] = 'stones'
        with self.assertRaises(ValueError):
            sleep.import_samples(payload, self.now)
        self.assertEqual(self.doc, {'nights': []})

    def test_pounds_convert_and_failed_persistence_is_not_success(self):
        payload = self.export()
        payload['additional']['body']['units']['bodyMass'] = 'lb'
        payload['additional']['body']['daily'][0]['values']['bodyMass'] = 200
        self.assertEqual(weight.normalize_weights(payload, self.now)[0]['weight'], 90.72)
        with patch.object(sleep, '_write', side_effect=RuntimeError('cloud down')):
            with self.assertRaises(RuntimeError):
                sleep.import_samples(payload, self.now)

    def test_authenticated_overlay_does_not_mutate_shared_report_or_use_later_weights(self):
        sleep.import_samples(self.export(), self.now)
        report = weekly._collect(fake_coach(False), date(2026, 10, 19), date(2026, 10, 26))
        original = copy.deepcopy(report)
        health = sleep.get_summary(date(2026, 10, 19), date(2026, 10, 26))
        result = weight.apply_report(report, health)
        self.assertEqual(report, original)
        self.assertEqual(result['goal_forecast']['current_weight'], 96)
        self.assertEqual(result['goal_forecast']['source'], 'apple_health')
        self.assertIsNone(result['weight_change'])
        self.assertIs(weight.apply_report(report, None), report)
        report['period_end'] = '2026-11-01'
        result = weight.apply_report(report, health)
        self.assertEqual(result['goal_forecast']['current_weight'], 95)
        self.assertEqual(result['goal_forecast']['rate_kg_week'], 1)
        self.assertEqual(result['weight_change'], -1)

    def test_health_weight_context_is_only_loaded_after_authorization(self):
        class HttpError(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
        access = isolated_function('api.py', '_sleep_access', {'HTTPException': HttpError})
        with patch.object(sleep, 'authorize', side_effect=PermissionError('wrong key')), patch.object(sleep, 'get_summary') as read:
            with self.assertRaises(HttpError):
                access(types.SimpleNamespace(headers={'authorization': 'Bearer wrong'}))
            self.assertIsNone(access(types.SimpleNamespace(headers={})))
            read.assert_not_called()

    def test_health_report_skips_unneeded_yazio_weight_fetch(self):
        coach = fake_coach()
        coach.yazio.client = object()
        coach.yazio._execute_with_retry = Mock(side_effect=AssertionError('YAZIO weight must not be fetched'))
        weekly._collect(coach, date(2026, 10, 19), date(2026, 10, 26), include_weights=False)
        coach.yazio._execute_with_retry.assert_not_called()

    def test_weekly_json_and_image_use_the_same_authenticated_weight_overlay(self):
        sleep.import_samples(self.export(), self.now)
        report = weekly._collect(fake_coach(False), date(2026, 10, 19), date(2026, 10, 26))
        report['period_end'] = '2026-11-01'
        health = sleep.get_summary(date(2026, 10, 19), date(2026, 10, 26))
        request = types.SimpleNamespace(headers={'authorization': 'Bearer test'})
        namespace = {'Request': object, 'Optional': __import__('typing').Optional,
                     'coach': fake_coach(False), 'timedelta': __import__('datetime').timedelta,
                     '_sleep_access': lambda *a: health, 'HTTPException': RuntimeError,
                     'JSONResponse': lambda data, **kw: data,
                     'Response': lambda data, **kw: data}
        get = isolated_function('api.py', 'get_weekly', namespace)
        image = isolated_function('api.py', 'get_weekly_image', namespace)
        with patch.object(weekly, 'summary', return_value=report), patch.object(weekly, 'week_start', return_value=date(2026, 10, 19)), patch.object(weekly, 'render_image', return_value=b'png') as render:
            actual = get(request, '2026-10-19')
            self.assertEqual(actual['goal_forecast']['current_weight'], 95)
            self.assertEqual(image(request, '2026-10-19'), b'png')
            self.assertEqual(render.call_args.args[0], actual)
            self.assertNotEqual(report['goal_forecast']['current_weight'], 95)


if __name__ == '__main__':
    unittest.main()
