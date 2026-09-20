import unittest
from analyzer import estimate_1rm, classify_muscle_group, WorkoutAnalyzer
from hevy_client import HevyClient
from storage import Storage
from coach import AIHevyCoach

class TestHevyCoach(unittest.TestCase):

    def test_estimate_1rm(self):
        # 100 kg for 10 reps -> 100 * (1 + 10/30) = 133.3 kg
        self.assertAlmostEqual(estimate_1rm(100, 10), 133.3, places=1)
        self.assertEqual(estimate_1rm(100, 1), 100.0)
        self.assertEqual(estimate_1rm(0, 10), 0.0)

    def test_classify_muscle_group(self):
        self.assertEqual(classify_muscle_group("Bench Press (Barbell)"), "Грудь")
        self.assertEqual(classify_muscle_group("Lat Pulldown (Cable)"), "Спина")
        self.assertEqual(classify_muscle_group("Deadlift (Barbell)"), "Задняя поверхность / Ягодицы")
        self.assertEqual(classify_muscle_group("Leg Press (Machine)"), "Квадрицепсы / Ноги")
        self.assertEqual(classify_muscle_group("Treadmill"), "Кардио")
        self.assertEqual(classify_muscle_group("Shoulder Press (Dumbbell)"), "Плечи")

    def test_client_count(self):
        client = HevyClient()
        count = client.get_workouts_count()
        self.assertGreaterEqual(count, 3)

    def test_storage_and_sync(self):
        storage = Storage()
        res = storage.sync_all(verbose=False)
        self.assertGreaterEqual(res["workouts_count"], 3)
        self.assertGreaterEqual(res["routines_count"], 5)

    def test_coach_outputs(self):
        coach = AIHevyCoach(auto_sync=False)
        last_review = coach.review_last_workout()
        self.assertIn("Пятница", last_review)
        self.assertIn("Становая тяга", last_review)

        next_preview = coach.preview_next_workout()
        self.assertIn("Понедельник", next_preview)

        weekly = coach.weekly_overview()
        self.assertIn("Всего тренировок", weekly)

if __name__ == "__main__":
    unittest.main()
