"""Verify the live AI call paths receive the concise policy, without starting a bot or contacting Gemini."""
import sys
import types
import unittest
from typing import Dict, List, Optional
from unittest.mock import Mock, patch

from response_style import CONCISE_STYLE, WORKOUT_FOCUS
from test_push import isolated_function


class ResponseStyleTests(unittest.TestCase):
    def general(self, generate, coach=None):
        client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=generate))
        module = types.SimpleNamespace(genai=types.SimpleNamespace(Client=Mock(return_value=client)))
        fn = isolated_function("bot.py", "ask_gemini_ai", {
            "Optional": Optional, "List": List, "Dict": Dict, "GEMINI_KEY": "test-only",
            "MODELS_CASCADE": ["first", "fallback"], "get_system_instruction": lambda: "Base athlete context",
            "coach": coach,
        })
        return fn, module

    def test_app_chat_and_sleep_analysis_keep_question_history_and_facts_with_concise_style(self):
        generate = Mock(return_value=types.SimpleNamespace(text="Короткий ответ"))
        fn, module = self.general(generate)
        with patch.dict(sys.modules, {"google": module}):
            answer = fn("Что скажешь о моём сне?", force_llm=True,
                        history=[{"role": "model", "text": "Предыдущий длинный ответ"}],
                        extra_context="Sleep: one recorded night, 482 minutes")
        self.assertEqual(answer, "Короткий ответ")
        args = generate.call_args.kwargs
        system = args["config"]["system_instruction"]
        self.assertIn(CONCISE_STYLE, system)
        self.assertIn("Sleep: one recorded night, 482 minutes", system)
        self.assertGreater(system.index(CONCISE_STYLE), system.index("482 minutes"))
        self.assertIn("Что скажешь о моём сне?", args["contents"])
        self.assertIn("Предыдущий длинный ответ", args["contents"])

    def test_fallback_model_has_the_same_style_and_detailed_requests_are_preserved(self):
        generate = Mock(side_effect=[RuntimeError("model unavailable"), types.SimpleNamespace(text="Подробный ответ")])
        fn, module = self.general(generate)
        question = "Объясни подробно и пошагово, как составить план"
        with patch.dict(sys.modules, {"google": module}):
            self.assertEqual(fn(question, force_llm=True), "Подробный ответ")
        self.assertEqual(generate.call_count, 2)
        for call in generate.call_args_list:
            self.assertIn(CONCISE_STYLE, call.kwargs["config"]["system_instruction"])
            self.assertIn(question, call.kwargs["contents"])

    def feedback(self, generate, configured=True):
        workout = {"id": "workout-1"}
        coach = types.SimpleNamespace(workouts=[workout], analyzer=types.SimpleNamespace(
            get_latest_workout=lambda: workout,
            analyze_workout=lambda w: {"title": "Ноги", "date": "26.10.2026", "duration_minutes": 77.5,
                                       "total_tonnage_kg": 13000, "total_working_sets": 20, "exercises": []}))
        client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=generate))
        module = types.SimpleNamespace(genai=types.SimpleNamespace(Client=Mock(return_value=client)))
        fn = isolated_function("bot.py", "analyze_post_workout_feedback", {
            "Optional": Optional, "coach": coach, "GEMINI_KEY": "test-only" if configured else "",
            "MODELS_CASCADE": ["first"],
        })
        from functools import partial
        return partial(fn, daily_context='{"completed": ["Зал"], "not_marked_today": ["Кодинг"]}'), module

    def test_workout_feedback_no_longer_requires_four_generic_sections(self):
        generate = Mock(return_value=types.SimpleNamespace(text="Разберём пропущенное упражнение."))
        fn, module = self.feedback(generate)
        feedback = "Не сделал становую: штанга была занята. Что изменить?"
        with patch.dict(sys.modules, {"google": module}):
            reply = fn(feedback, "workout-1")
        self.assertIn("Разберём пропущенное упражнение.", reply)
        prompt = generate.call_args.kwargs["contents"]
        self.assertIn(feedback, prompt)
        self.assertIn("13,000", prompt)
        self.assertIn("77.5", prompt)
        self.assertIn(CONCISE_STYLE, prompt)
        self.assertIn(WORKOUT_FOCUS, prompt)
        self.assertNotIn("Сформируй структурированный", prompt)
        self.assertNotIn("Если суставы в порядке — похвали технику", prompt)

    def test_unavailable_ai_returns_facts_without_invented_recovery_advice(self):
        fn, module = self.feedback(Mock(), configured=False)
        with patch.dict(sys.modules, {"google": module}):
            reply = fn("Штанга была занята")
        self.assertIn("ИИ сейчас недоступен", reply)
        self.assertIn("Штанга была занята", reply)
        self.assertNotIn("электролит", reply)
        self.assertNotIn("растяж", reply)
        self.assertNotIn("надёжно сохранён", reply)

    def test_existing_direct_command_does_not_start_ai(self):
        generate = Mock()
        coach = types.SimpleNamespace(get_sunday_weekly_table_report=lambda: "Таблица недели")
        fn, module = self.general(generate, coach)
        with patch.dict(sys.modules, {"google": module}):
            self.assertEqual(fn("/weekly"), "Таблица недели")
        generate.assert_not_called()

    def test_focused_analysis_tries_every_model_and_accepts_the_last_fallback(self):
        generate = Mock(side_effect=[RuntimeError("deadline exceeded")] * 4 + [types.SimpleNamespace(text="Ответ последней модели")])
        fn, module = self.general(generate)
        models = ["first", "gemini-flash-lite-latest", "third", "fourth", "fifth"]
        fn.__globals__["MODELS_CASCADE"] = models
        fn.__globals__["get_system_instruction"] = Mock(side_effect=AssertionError("No full context collection"))
        with patch.dict(sys.modules, {"google": module}):
            reply = fn("Разбери сон", force_llm=True, extra_context="One recorded night", context_only=True)
        self.assertEqual(reply, "Ответ последней модели")
        self.assertEqual([call.kwargs["model"] for call in generate.call_args_list], models)
        fn.__globals__["get_system_instruction"].assert_not_called()
        http = module.genai.Client.call_args.kwargs["http_options"]
        self.assertEqual(http, {"timeout": 18000})
        self.assertIn("One recorded night", generate.call_args.kwargs["config"]["system_instruction"])


if __name__ == "__main__":
    unittest.main()
