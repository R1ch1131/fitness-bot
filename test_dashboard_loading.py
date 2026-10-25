"""Verify the initial marks request does not wait for external integrations."""
import ast
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from habits_manager import HabitsManager
from config import DATA_DIR


class LoadingTests(unittest.TestCase):
    def test_slow_sync_does_not_overwrite_a_new_manual_mark(self):
        with tempfile.TemporaryDirectory(dir=DATA_DIR) as tmp, patch("cloud_storage.set_cloud_data"):
            manager = HabitsManager.__new__(HabitsManager)
            manager.file_path = Path(tmp) / "habits.json"
            manager.file_path.write_text(json.dumps([
                {"id": "reading", "title": "Чтение", "category": "Чтение", "history": {}},
                {"id": "calories", "title": "Питание", "category": "Питание", "history": {}},
            ]), encoding="utf-8")
            yazio = Mock()
            def delayed_meals(_date):
                manager.toggle_day("reading", "2026-10-25")
                return {"meals": {"breakfast": ["food"]}}
            yazio.get_consumed_products.side_effect = delayed_meals
            yazio.get_weekly_nutrition.return_value = {"days": []}
            manager.sync_with_hevy_and_yazio(types.SimpleNamespace(workouts=[], yazio=yazio))
            reading = next(h for h in manager.get_habits() if h["id"] == "reading")
            self.assertTrue(reading["history"]["2026-10-25"])
            # The following sync, without a concurrent edit, still applies auto marks.
            yazio.get_consumed_products.side_effect = None
            yazio.get_consumed_products.return_value = {"meals": {"breakfast": ["food"]}}
            manager.sync_with_hevy_and_yazio(types.SimpleNamespace(workouts=[], yazio=yazio))
            calories = next(h for h in manager.get_habits() if h["id"] == "calories")
            self.assertIn(True, calories["history"].values())

    def test_marks_return_without_hevy_or_yazio_sync(self):
        tree = ast.parse(Path(__file__).with_name("api.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_habits")
        node.decorator_list = []
        manager = Mock()
        manager.get_habits.return_value = [{"id": "reading", "history": {"2026-10-25": True}}]
        manager.get_habits_ai_summary.return_value = "1 из 1"
        manager.sync_with_hevy_and_yazio.side_effect = AssertionError("External sync blocks initial load")
        namespace = {"habits_mgr": manager}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "api.py", "exec"), namespace)
        self.assertEqual(namespace["get_habits"]()["habits"][0]["history"], {"2026-10-25": True})
        manager.sync_with_hevy_and_yazio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
