import copy
import io
import os
import sys
import types
import unittest
from datetime import date, datetime
from unittest.mock import Mock, patch

import sleep_data as sleep
import weekly_reports as weekly
from notification_settings import TZ
from test_push import isolated_function


class SleepTests(unittest.TestCase):
    def setUp(self):
        self.doc = {"nights": []}
        self.read = patch.object(sleep, "_read", side_effect=lambda *args: copy.deepcopy(self.doc))
        self.write = patch.object(sleep, "_write", side_effect=lambda name, doc: self.doc.update(copy.deepcopy(doc)))
        self.read.start(); self.write.start()
        self.addCleanup(self.read.stop); self.addCleanup(self.write.stop)
        self.now = datetime(2026, 10, 26, 12, tzinfo=TZ)

    def sample(self, start, end, stage):
        return {"start": start, "end": end, "stage": stage}

    def test_midnight_duplicate_devices_and_generic_sleep_do_not_inflate_duration(self):
        detailed = self.sample("2026-10-25T23:00:00+06:00", "2026-10-26T07:00:00+06:00", "core")
        body = {"samples": [detailed, detailed,
                self.sample("2026-10-25T23:00:00+06:00", "2026-10-26T07:00:00+06:00", "asleep"),
                self.sample("2026-10-25T22:00:00+06:00", "2026-10-26T08:00:00+06:00", "in_bed")]}
        sleep.import_samples(body, self.now)
        self.assertEqual(len(self.doc["nights"]), 1)
        night = self.doc["nights"][0]
        self.assertEqual(night["date"], "2026-10-26")
        self.assertEqual(night["sleep_minutes"], 480)
        self.assertEqual(night["asleep_minutes"], 0)
        sleep.import_samples(body, self.now)
        self.assertEqual(self.doc["nights"], [night])

    def test_awake_is_not_sleep_and_phases_are_disjoint(self):
        body = {"samples": [
            self.sample("2026-10-26T00:00:00Z", "2026-10-26T01:00:00Z", "asleepDeep"),
            self.sample("2026-10-26T00:30:00Z", "2026-10-26T01:30:00Z", 5),
            self.sample("2026-10-26T01:30:00Z", "2026-10-26T02:00:00Z", "awake")]}
        sleep.import_samples(body, self.now)
        n = self.doc["nights"][0]
        self.assertEqual((n["sleep_minutes"], n["deep_minutes"], n["rem_minutes"], n["awake_minutes"]), (90, 60, 30, 30))

    def test_in_bed_only_is_missing_sleep_not_zero(self):
        sleep.import_samples({"samples": [self.sample("2026-10-25T23:00:00+06:00", "2026-10-26T07:00:00+06:00", "in_bed")]}, self.now)
        summary = sleep.get_summary(date(2026, 10, 19), date(2026, 10, 26))
        self.assertEqual(summary["tracked_nights"], 0)
        self.assertIsNone(summary["average_minutes"])

    def test_bad_sample_rejects_entire_import_and_preserves_existing_data(self):
        good = self.sample("2026-10-25T23:00:00+06:00", "2026-10-26T07:00:00+06:00", "deep")
        for bad in [dict(good, stage="unknown"), dict(good, start="2026-10-25T23:00:00"),
                    dict(good, end="2026-10-27T07:00:00+06:00"), dict(good, end=good["start"])]:
            with self.assertRaises(ValueError):
                sleep.import_samples({"samples": [good, bad]}, self.now)
            self.assertEqual(self.doc, {"nights": []})
        with self.assertRaises(ValueError):
            sleep.import_samples({"samples": []}, self.now)

    def test_failed_cloud_write_is_not_success(self):
        with patch.object(sleep, "_write", side_effect=RuntimeError("cloud down")):
            with self.assertRaises(RuntimeError):
                sleep.import_samples({"samples": [self.sample("2026-10-25T23:00:00+06:00", "2026-10-26T07:00:00+06:00", "core")]}, self.now)

    def test_bearer_required_and_disabled_until_configured(self):
        with patch.dict(os.environ, {"HEALTH_IMPORT_TOKEN": "x" * 32}):
            sleep.authorize("Bearer " + "x" * 32)
            for header in [None, "Bearer wrong", "x" * 32]:
                with self.assertRaises(PermissionError):
                    sleep.authorize(header)
        with patch.dict(os.environ, {"HEALTH_IMPORT_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                sleep.authorize(None)

    def test_delete_removes_imported_history(self):
        self.doc.update({"nights": [{"date": "2026-10-26", "sleep_minutes": 480}]})
        sleep.delete_data()
        self.assertEqual(self.doc["nights"], [])

    def kit_export(self):
        # Synthetic schema-2 example. Never commit the user's health export as a fixture.
        return {"meta": {"app": "Health Export Kit", "schemaVersion": 2, "timeZone": "Asia/Omsk",
                         "rangeStart": "2026-10-19T12:00:00Z", "rangeEnd": "2026-10-26T12:00:00Z"},
                "sleep": {"sessions": [{"start": "10-21 23:00:00", "end": "10-22 07:00:00", "stages": [
                    {"start": "10-21 23:00:00", "end": "10-22 00:00:00", "stage": "asleepCore"},
                    {"start": "10-22 00:00:00", "end": "10-22 01:00:00", "stage": "asleepDeep"},
                    {"start": "10-22 01:00:00", "end": "10-22 07:00:00", "stage": "asleepREM"}]}]},
                "additional": {"medications": ["not imported"]}, "activity": {"steps": 12345}}

    def test_health_export_kit_yearless_stages_and_retry(self):
        value = self.kit_export()
        result = sleep.import_samples(value, self.now)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["imported_nights"], 1)
        night = self.doc["nights"][0]
        self.assertEqual((night["date"], night["sleep_minutes"]), ("2026-10-22", 480))
        self.assertEqual((night["core_minutes"], night["deep_minutes"], night["rem_minutes"]), (60, 60, 360))
        first = copy.deepcopy(self.doc)
        sleep.import_samples(value, self.now)
        self.assertEqual(self.doc, first)
        self.assertNotIn("additional", self.doc)
        self.assertNotIn("not imported", str(self.doc))

    def test_health_export_kit_new_year_uses_range_not_current_year(self):
        value = self.kit_export()
        value["meta"].update({"rangeStart": "2026-12-29T00:00:00Z", "rangeEnd": "2027-01-03T00:00:00Z"})
        session = value["sleep"]["sessions"][0]
        session.update(start="12-31 23:00:00", end="01-01 07:00:00")
        session["stages"] = [{"start": session["start"], "end": session["end"], "stage": "asleepCore"}]
        sleep.import_samples(value, datetime(2027, 1, 4, tzinfo=TZ))
        self.assertEqual(self.doc["nights"][0]["date"], "2027-01-01")
        self.assertEqual(self.doc["nights"][0]["sleep_minutes"], 480)

    def test_health_export_kit_rejects_outside_session_unknown_schema_and_empty_sleep(self):
        for change in ("stage", "schema", "empty", "zone"):
            value = self.kit_export()
            if change == "stage":
                value["sleep"]["sessions"][0]["stages"][0]["start"] = "10-20 23:00:00"
            if change == "schema":
                value["meta"]["schemaVersion"] = 99
            if change == "empty":
                value["sleep"]["sessions"] = []
            if change == "zone":
                value["meta"]["timeZone"] = "not/a/timezone"
            with self.assertRaises(ValueError):
                sleep.import_samples(value, self.now)
            self.assertEqual(self.doc, {"nights": []})

    def test_health_export_kit_unrecorded_gaps_are_not_sleep(self):
        value = self.kit_export()
        session = value["sleep"]["sessions"][0]
        session["asleepSec"] = 999999
        session["stages"].pop(1)
        sleep.import_samples(value, self.now)
        self.assertEqual(self.doc["nights"][0]["sleep_minutes"], 420)

    def test_export_metadata_notes_are_not_instructions_or_ai_context(self):
        value = self.kit_export()
        value["meta"]["notes"] = "untrusted instructions in export metadata"
        sleep.import_samples(value, self.now)
        context = sleep.ai_context(sleep.get_summary(date(2026, 10, 19), date(2026, 10, 25)))
        self.assertNotIn("untrusted instructions", context)
        self.assertNotIn("not imported", context)


def fake_coach(configured=True):
    return types.SimpleNamespace(
        workouts=[{"title": "Ноги", "start_time": "2026-10-20T23:00:00Z", "end_time": "2026-10-21T00:00:00Z"},
                  {"title": "Не завершена", "start_time": "2026-10-21T23:00:00Z"}],
        analyzer=types.SimpleNamespace(analyze_workout=lambda w: {"total_tonnage_kg": 5200}),
        yazio=types.SimpleNamespace(is_configured=lambda: configured, client=None,
            get_daily_summary=lambda day: {"calories": 2000, "protein": 160, "fat": 60, "carbs": 200} if day.day == 20 else {}))


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        weekly._analysis_cache.clear()

    def test_actual_calendar_week_and_only_logged_days_in_average(self):
        report = weekly._collect(fake_coach(), date(2026, 10, 19), date(2026, 10, 26))
        self.assertEqual((report["period_start"], report["period_end"]), ("2026-10-19", "2026-10-25"))
        self.assertEqual(report["averages"]["calories"], 2000)
        self.assertEqual(report["averages"]["tracked_days"], 1)
        self.assertEqual((report["workout_count"], report["tonnage_kg"]), (1, 5200))
        self.assertIsNone(report["weight_change"])
        self.assertEqual(report["days"][2]["workout_titles"], ["Ноги"])

    def test_empty_data_does_not_fabricate_weight_calories_or_protein(self):
        report = weekly._collect(fake_coach(False), date(2026, 10, 26), date(2026, 10, 26))
        self.assertIsNone(report["averages"]["calories"])
        self.assertIsNone(report["averages"]["protein"])
        self.assertIsNone(report["weight_change"])
        self.assertTrue(report["days"][1]["is_future"])

    def test_cache_avoids_repeated_external_calls_and_can_be_invalidated(self):
        coach = fake_coach()
        weekly.clear_cache()
        with patch.object(weekly, "_collect", return_value={"days": []}) as collect:
            weekly.summary(coach, date(2026, 10, 19)); weekly.summary(coach, date(2026, 10, 19))
            self.assertEqual(collect.call_count, 1)
            weekly.clear_cache(); weekly.summary(coach, date(2026, 10, 19))
            self.assertEqual(collect.call_count, 2)

    def test_report_is_valid_png_with_and_without_sleep(self):
        from PIL import Image
        report = weekly._collect(fake_coach(), date(2026, 10, 19), date(2026, 10, 26))
        for data in [None, {"tracked_nights": 7, "average_minutes": 459}]:
            image = Image.open(io.BytesIO(weekly.render_image(report, data)))
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (1080, 1560))

    def test_unauthorized_request_never_loads_sleep_data(self):
        class HTTPError(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
        access = isolated_function("api.py", "_sleep_access", {"HTTPException": HTTPError})
        with patch.dict(os.environ, {"HEALTH_IMPORT_TOKEN": "x" * 32}), patch.object(sleep, "get_summary") as read:
            self.assertIsNone(access(types.SimpleNamespace(headers={})))
            with self.assertRaises(HTTPError) as caught:
                access(types.SimpleNamespace(headers={}), required=True)
            self.assertEqual(caught.exception.status_code, 401)
            read.assert_not_called()

    def test_week_analysis_gets_selected_week_and_only_authorized_sleep(self):
        ask = Mock(return_value="Три задачи на следующую неделю")
        report = weekly._collect(fake_coach(), date(2026, 10, 19), date(2026, 10, 26))
        fn = isolated_function("api.py", "analyze_week", {
            "Request": object, "Optional": __import__("typing").Optional, "coach": fake_coach(),
            "_sleep_access": lambda *args: None, "json": __import__("json"),
            "time": __import__("time"),
            "timedelta": __import__("datetime").timedelta, "HTTPException": RuntimeError})
        with patch.dict(sys.modules, {"bot": types.SimpleNamespace(ask_gemini_ai=ask)}), patch.object(weekly, "summary", return_value=report):
            result = fn(object(), "2026-10-19")
        self.assertEqual(result["period_start"], "2026-10-19")
        context = ask.call_args.kwargs["extra_context"]
        self.assertIn("2026-10-19", context)
        self.assertIn("Пользователь не подключил данные сна", context)

    def test_chat_history_is_protected_when_health_is_enabled(self):
        access = Mock(side_effect=PermissionError("unauthorized"))
        namespace = {"Request": object, "Dict": __import__("typing").Dict,
                     "Any": __import__("typing").Any, "_sleep_access": access}
        with patch.object(sleep, "is_configured", return_value=True):
            for name in ("get_chat_history", "save_chat_history"):
                fn = isolated_function("api.py", name, namespace)
                with self.assertRaises(PermissionError):
                    fn(object()) if name == "get_chat_history" else fn({"messages": []}, object())

    def test_selected_week_sleep_is_added_to_ai_context_without_the_secret(self):
        ask = Mock(return_value="Длительность сна и режим")
        secret = "secret-that-must-not-reach-the-model"
        health = {"tracked_nights": 2, "average_minutes": 450, "nights": []}
        fn = isolated_function("api.py", "analyze_week", {
            "Request": object, "Optional": __import__("typing").Optional, "coach": fake_coach(),
            "_sleep_access": lambda *args: health, "json": __import__("json"),
            "time": __import__("time"),
            "timedelta": __import__("datetime").timedelta, "HTTPException": RuntimeError})
        with patch.dict(sys.modules, {"bot": types.SimpleNamespace(ask_gemini_ai=ask)}), patch.object(weekly, "summary", return_value={}):
            fn(types.SimpleNamespace(headers={"authorization": secret}), "2026-10-19", "sleep")
        self.assertIn("сон", ask.call_args.args[0])
        self.assertIn('"average_minutes": 450', ask.call_args.kwargs["extra_context"])
        self.assertNotIn(secret, str(ask.call_args))

    def test_sleep_analysis_does_not_fetch_nutrition_and_reuses_successful_reply(self):
        ask = Mock(return_value="Одна ночь записана; вывод о всей неделе сделать нельзя.")
        health = {"tracked_nights": 1, "average_minutes": 480, "nights": [{"date": "2026-10-22", "sleep_minutes": 480}]}
        fn = isolated_function("api.py", "analyze_week", {
            "Request": object, "Optional": __import__("typing").Optional, "coach": fake_coach(),
            "_sleep_access": lambda *args: health, "json": __import__("json"), "time": __import__("time"),
            "timedelta": __import__("datetime").timedelta, "HTTPException": RuntimeError})
        with patch.dict(sys.modules, {"bot": types.SimpleNamespace(ask_gemini_ai=ask)}), patch.object(weekly, "summary", side_effect=AssertionError("No YAZIO calls for sleep")):
            first = fn(object(), "2026-10-19", "sleep")
            second = fn(object(), "2026-10-19", "sleep")
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(ask.call_count, 1)
            self.assertTrue(ask.call_args.kwargs["context_only"])
            health["average_minutes"] = 420
            third = fn(object(), "2026-10-19", "sleep")
            self.assertFalse(third["cached"])
            self.assertEqual(ask.call_count, 2)


if __name__ == "__main__":
    unittest.main()
