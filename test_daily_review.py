import json
import sys
import time
import types
import unittest
from datetime import datetime
from typing import Dict, Optional, List, Any
from unittest.mock import Mock, patch

from daily_review import TZ, collect_daily_review, is_workout_checkin
from response_style import post_workout_prompt
from test_push import isolated_function


class DailyReviewTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime(2026, 10, 26, 21, tzinfo=TZ)
        self.habits = [
            {"id": "gym", "title": "Зал", "target_days": 5, "history": {"2026-10-26": True}},
            {"id": "reading", "title": "Чтение", "target_days": 7, "history": {"2026-10-26": True}},
            {"id": "coding", "title": "Кодинг", "target_days": 7, "history": {"2026-10-25": True}},
            {"id": "stretching", "title": "Растяжка", "target_days": 3, "history": {}},
        ]
        self.hm = types.SimpleNamespace(get_habits=lambda: self.habits)
        self.book = {"title": "Пример книги", "status": "reading", "current_page": 170, "total_pages": 384,
                     "notes": "Секретный будущий сюжет, который нельзя использовать"}
        self.bm = types.SimpleNamespace(get_books=lambda: [self.book])
        self.coach = types.SimpleNamespace(yazio=types.SimpleNamespace(is_configured=lambda: True,
            get_daily_summary=lambda day: {"calories": 1800, "protein": 130, "goals": {"calories": 2000, "protein": 160}}))

    def test_review_uses_fresh_today_marks_nutrition_and_weekly_targets(self):
        text, reading = collect_daily_review(self.coach, self.hm, self.bm, self.today)
        facts = json.loads(text)
        self.assertEqual(facts["completed"], ["Зал", "Чтение"])
        self.assertEqual(facts["not_marked_today"], ["Кодинг"])
        self.assertEqual(facts["weekly_targets"], [{"title": "Растяжка", "target_days": 3}])
        self.assertEqual(facts["nutrition"]["protein"], 130)
        self.assertIn("170/384", reading)
        self.assertIn("44%", reading)
        self.assertIn("осталось 214", reading)
        self.assertIn("Чтение на сегодня отмечено", reading)
        self.habits[2]["history"]["2026-10-26"] = True
        updated, _ = collect_daily_review(self.coach, self.hm, self.bm, self.today)
        self.assertIn("Кодинг", json.loads(updated)["completed"])

    def test_book_title_notes_and_plot_never_enter_generative_daily_prompt(self):
        text, reading = collect_daily_review(self.coach, self.hm, self.bm, self.today)
        prompt = post_workout_prompt("Тренировка: ноги", "Все нормально", text)
        self.assertNotIn(self.book["title"], prompt)
        self.assertNotIn(self.book["notes"], prompt)
        self.assertNotIn(self.book["notes"], reading)
        self.assertNotIn("сегодня прочитал 170", reading)

    def test_unavailable_sources_do_not_invent_completed_tasks_or_books(self):
        broken = types.SimpleNamespace(get_habits=Mock(side_effect=RuntimeError("offline")))
        books = types.SimpleNamespace(get_books=Mock(side_effect=RuntimeError("offline")))
        text, reading = collect_daily_review(self.coach, broken, books, self.today)
        facts = json.loads(text)
        self.assertEqual(facts["habits_status"], "unavailable")
        self.assertNotIn("completed", facts)
        self.assertEqual(reading, "")

    def test_weekend_does_not_treat_builtin_gym_as_an_unfinished_daily_task(self):
        text, _ = collect_daily_review(self.coach, self.hm, self.bm, datetime(2026, 10, 25, 21, tzinfo=TZ))
        self.assertNotIn("Зал", json.loads(text)["not_marked_today"])

    def test_only_workout_feedback_uses_daily_review_not_unrelated_or_followup_questions(self):
        pending = {"responded": False, "due_time": 10000}
        self.assertTrue(is_workout_checkin("Не сделал становую, штанга была занята", pending, 10100))
        self.assertTrue(is_workout_checkin("Чувствую себя нормально", pending, 10100))
        self.assertFalse(is_workout_checkin("Что съесть после тренировки?", pending, 10100))
        self.assertFalse(is_workout_checkin("Какую книгу почитать?", pending, 10100))
        self.assertFalse(is_workout_checkin("Как спал сегодня?", pending, 10100))
        self.assertFalse(is_workout_checkin("После жима устал", dict(pending, responded=True), 10100))
        self.assertFalse(is_workout_checkin("Нормально", pending, 100000))

    def test_bot_feedback_appends_only_the_server_generated_reading_line(self):
        generate = Mock(return_value=types.SimpleNamespace(text="Зал отмечен. Кодинг пока не отмечен."))
        from test_response_style import ResponseStyleTests
        fn, module = ResponseStyleTests().feedback(generate)
        _, reading = collect_daily_review(self.coach, self.hm, self.bm, self.today)
        with patch.dict(sys.modules, {"google": module}):
            reply = fn("Ноги устали", reading_progress=reading)
        self.assertTrue(reply.endswith(reading))
        self.assertNotIn(self.book["title"], generate.call_args.kwargs["contents"])

    def test_workout_review_keeps_habits_nutrition_sleep_and_reading_after_sleep_optimization(self):
        generate = Mock(return_value=types.SimpleNamespace(text="Краткий итог дня"))
        from test_response_style import ResponseStyleTests
        fn, module = ResponseStyleTests().feedback(generate)
        facts, reading = collect_daily_review(self.coach, self.hm, self.bm, self.today)
        with patch.dict(sys.modules, {"google": module}):
            reply = fn("Ноги устали", daily_context=facts, reading_progress=reading,
                       extra_context='Сон Apple Watch: 480 минут, одна ночь с данными.')
        prompt = generate.call_args.kwargs["contents"]
        self.assertIn('"completed": ["Зал", "Чтение"]', prompt)
        self.assertIn('"not_marked_today": ["Кодинг"]', prompt)
        self.assertIn('"calories": 1800', prompt)
        self.assertIn('Сон Apple Watch: 480 минут', prompt)
        self.assertIn('170/384', reply)
        self.assertTrue(reply.endswith(reading))

    def test_app_routes_checkin_with_fresh_context_and_does_not_acknowledge_a_book_question(self):
        for message, is_feedback in [("После жима чувствую усталость", True), ("Какую книгу почитать?", False)]:
            pending = {"responded": False, "due_time": time.time(), "workout_id": "w1"}
            ask, analyze, save = Mock(return_value="обычный ответ"), Mock(return_value="итог дня"), Mock()
            module = types.SimpleNamespace(ask_gemini_ai=ask, analyze_post_workout_feedback=analyze,
                                           load_pending_checkin=lambda: pending, save_pending_checkin=save)
            fn = isolated_function("api.py", "chat_with_coach", {
                "ChatRequest": object, "Request": object, "_sleep_access": lambda r: None,
                "habits_mgr": types.SimpleNamespace(sync_with_hevy_and_yazio=Mock()), "books_mgr": self.bm,
                "coach": self.coach, "time": time, "HTTPException": RuntimeError})
            with patch.dict(sys.modules, {"bot": module}), patch("daily_review.collect_daily_review", return_value=('{}', '170/384 стр.')):
                result = fn(types.SimpleNamespace(message=message, history=[]), object())
            if is_feedback:
                self.assertEqual(result["reply"], "итог дня")
                self.assertEqual(analyze.call_args.kwargs["reading_progress"], "170/384 стр.")
                save.assert_called_once()
                ask.assert_not_called()
            else:
                self.assertEqual(result["reply"], "обычный ответ")
                save.assert_not_called()
                analyze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
