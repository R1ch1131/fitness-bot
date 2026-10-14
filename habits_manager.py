import os
import json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import DATA_DIR

HABITS_FILE = DATA_DIR / "habits.json"
TZ_GMT6 = timezone(timedelta(hours=6))

DEFAULT_HABITS = [
    {
        "id": "calories",
        "title": "Счет калорий (дефицит ~2000 ккал)",
        "category": "Питание",
        "target_days": 7,
        "history": {},
        "created_at": "2026-10-14"
    },
    {
        "id": "gym",
        "title": "Зал по будням (Hevy)",
        "category": "Спорт",
        "target_days": 5,
        "history": {},
        "created_at": "2026-10-14"
    },
    {
        "id": "reading",
        "title": "Чтение: не менее 10 страниц",
        "category": "Чтение",
        "target_days": 7,
        "history": {},
        "created_at": "2026-10-14"
    },
    {
        "id": "coding",
        "title": "Занятие прогой: минимум 30 мин",
        "category": "Учеба / Код",
        "target_days": 7,
        "history": {},
        "created_at": "2026-10-14"
    }
]

class HabitsManager:
    def __init__(self):
        self.file_path = HABITS_FILE
        self._ensure_file()

    def _ensure_file(self):
        try:
            from cloud_storage import get_cloud_data
            cloud_habits = get_cloud_data("athlete_habits")
            if cloud_habits and isinstance(cloud_habits, list):
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(cloud_habits, f, ensure_ascii=False, indent=2)
                return
        except Exception as ce:
            print(f"Cloud check note in habits_manager: {ce}")

        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_HABITS, f, ensure_ascii=False, indent=2)

    def sync_with_hevy_and_yazio(self, coach) -> List[Dict[str, Any]]:
        """Automatically marks habit progress:
        - 'calories': marked True for dates where YAZIO has logged food (breakfast, meals, calories > 100).
        - 'gym': marked True for dates where Hevy has a completed workout.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                habits = json.load(f)
        except Exception:
            habits = DEFAULT_HABITS

        changed = False

        # 1. Sync Gym from Hevy workouts
        gym_habit = None
        for h in habits:
            if h.get("id") == "gym" or "зал" in h.get("title", "").lower() or "спорт" in h.get("category", "").lower():
                gym_habit = h
                break

        if gym_habit and coach and getattr(coach, "workouts", None):
            h_history = gym_habit.setdefault("history", {})
            for w in coach.workouts:
                start_time = w.get("start_time", "")
                if start_time and len(start_time) >= 10:
                    w_date = start_time[:10]
                    if not h_history.get(w_date):
                        h_history[w_date] = True
                        changed = True

        # 2. Sync Nutrition / Calorie tracking from YAZIO
        cal_habit = None
        for h in habits:
            if h.get("id") == "calories" or "калор" in h.get("title", "").lower() or "питан" in h.get("category", "").lower():
                cal_habit = h
                break

        if cal_habit and coach and getattr(coach, "yazio", None) and coach.yazio.is_configured():
            cal_history = cal_habit.setdefault("history", {})
            now_gmt6 = datetime.now(TZ_GMT6)
            today_date = now_gmt6.date()
            today_str = today_date.strftime("%Y-%m-%d")

            # Check today's food logging
            try:
                consumed = coach.yazio.get_consumed_products(today_date)
                meals = consumed.get("meals", {}) if consumed else {}
                has_meals = any(len(items) > 0 for items in meals.values())

                if not has_meals:
                    summary = coach.yazio.get_daily_summary(today_date)
                    if summary and summary.get("calories", 0) > 50:
                        has_meals = True

                if has_meals and not cal_history.get(today_str):
                    cal_history[today_str] = True
                    changed = True
            except Exception as e:
                print(f"Auto-sync today YAZIO error: {e}")

            # Check past 7 days from weekly nutrition
            try:
                wn = coach.yazio.get_weekly_nutrition(days_count=7)
                if wn and wn.get("days"):
                    year = today_date.year
                    for d in wn["days"]:
                        if d.get("is_logged") and d.get("calories", 0) > 100:
                            d_str = d.get("date", "")
                            if "." in d_str and len(d_str) == 5:
                                day, month = map(int, d_str.split("."))
                                full_date_str = f"{year}-{month:02d}-{day:02d}"
                            else:
                                full_date_str = d_str
                            
                            if not cal_history.get(full_date_str):
                                cal_history[full_date_str] = True
                                changed = True
            except Exception as e:
                print(f"Auto-sync weekly YAZIO error: {e}")

        if changed:
            self._save(habits)

        return self.get_habits()

    def get_habits(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                habits = json.load(f)
        except Exception:
            habits = DEFAULT_HABITS

        # Calculate streaks and metrics for each habit
        now_gmt6 = datetime.now(TZ_GMT6)
        today = now_gmt6.date()

        result = []
        for h in habits:
            streak, record = self._calculate_streak(h.get("history", {}), today)
            h_copy = dict(h)
            h_copy["current_streak"] = streak
            h_copy["record_streak"] = max(record, h.get("record_streak", 0))
            result.append(h_copy)
        return result

    def _calculate_streak(self, history: Dict[str, bool], today: date) -> tuple[int, int]:
        """Calculates current consecutive streak and all-time record streak."""
        if not history:
            return 0, 0

        # Check consecutive days backwards
        streak = 0
        cur_d = today

        # If today is completed, start streak from today
        today_str = today.strftime("%Y-%m-%d")
        if history.get(today_str):
            streak += 1
            cur_d = today - timedelta(days=1)
        else:
            # If today is not yet done, check if yesterday was done to keep streak alive
            yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            if history.get(yesterday_str):
                cur_d = today - timedelta(days=1)
            else:
                # Neither today nor yesterday done -> streak is 0
                return 0, self._calculate_all_time_record(history)

        while True:
            d_str = cur_d.strftime("%Y-%m-%d")
            if history.get(d_str):
                streak += 1
                cur_d -= timedelta(days=1)
            else:
                break

        record = max(streak, self._calculate_all_time_record(history))
        return streak, record

    def _calculate_all_time_record(self, history: Dict[str, bool]) -> int:
        if not history:
            return 0
        sorted_dates = sorted([datetime.strptime(k, "%Y-%m-%d").date() for k, v in history.items() if v])
        if not sorted_dates:
            return 0

        max_streak = 1
        cur_streak = 1
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
                cur_streak += 1
                if cur_streak > max_streak:
                    max_streak = cur_streak
            elif sorted_dates[i] > sorted_dates[i - 1] + timedelta(days=1):
                cur_streak = 1
        return max_streak

    def toggle_day(self, habit_id: str, date_str: str) -> Dict[str, Any]:
        habits = self.get_habits()
        target = None
        for h in habits:
            if h.get("id") == habit_id:
                target = h
                break

        if not target:
            raise ValueError(f"Привычка с id {habit_id} не найдена")

        history = target.setdefault("history", {})
        current_status = history.get(date_str, False)
        history[date_str] = not current_status

        # Save to file
        self._save(habits)
        return target

    def add_habit(self, title: str, category: str, target_days: int = 7) -> Dict[str, Any]:
        habits = self.get_habits()
        import uuid
        new_habit = {
            "id": str(uuid.uuid4())[:8],
            "title": title.strip(),
            "category": category.strip(),
            "target_days": target_days,
            "history": {},
            "created_at": datetime.now(TZ_GMT6).strftime("%Y-%m-%d")
        }
        habits.append(new_habit)
        self._save(habits)
        return new_habit

    def delete_habit(self, habit_id: str) -> bool:
        habits = self.get_habits()
        habits = [h for h in habits if h.get("id") != habit_id]
        self._save(habits)
        return True

    def edit_habit(self, habit_id: str, title: Optional[str] = None, category: Optional[str] = None, target_days: Optional[int] = None) -> Dict[str, Any]:
        habits = self.get_habits()
        target = None
        for h in habits:
            if h.get("id") == habit_id:
                if title:
                    h["title"] = title.strip()
                if category:
                    h["category"] = category.strip()
                if target_days:
                    h["target_days"] = target_days
                target = h
                break
        if not target:
            raise ValueError(f"Habit {habit_id} not found")
        self._save(habits)
        return target

    def _save(self, habits: List[Dict[str, Any]]):
        # Clean ephemeral fields before saving
        to_save = []
        for h in habits:
            h_copy = dict(h)
            h_copy.pop("current_streak", None)
            h_copy.pop("record_streak", None)
            to_save.append(h_copy)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
        try:
            from cloud_storage import set_cloud_data
            set_cloud_data("athlete_habits", to_save)
        except Exception:
            pass

    def get_habits_ai_summary(self, target_date: Optional[date] = None) -> str:
        """Formats habits status into clear text for Gemini AI prompt."""
        now = datetime.now(TZ_GMT6)
        d = target_date or now.date()
        d_str = d.strftime("%Y-%m-%d")
        habits = self.get_habits()

        lines = [f"📋 Привычки и цели атлета на {d_str}:"]
        completed_count = 0
        for h in habits:
            done = h.get("history", {}).get(d_str, False)
            if done:
                completed_count += 1
            status_emoji = "✅ Выполнено" if done else "❌ Еще не сделано"
            lines.append(f"• {h['title']} ({h['category']}): {status_emoji} | Текущий стрик: {h['current_streak']} дн. (Рекорд: {h['record_streak']} дн.)")

        percent = round((completed_count / len(habits)) * 100) if habits else 0
        lines.append(f"Итог за день: {completed_count} из {len(habits)} выполнено ({percent}%).")
        return "\n".join(lines)
