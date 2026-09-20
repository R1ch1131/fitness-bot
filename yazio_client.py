import os
import json
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pathlib import Path
from config import BASE_DIR, DATA_DIR

YAZIO_TOKEN_FILE = DATA_DIR / "yazio_token.txt"
NUTRITION_CACHE_FILE = DATA_DIR / "nutrition_cache.json"

class YazioManager:
    """Manager for retrieving nutrition and calorie data from YAZIO."""

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.email = email or os.getenv("YAZIO_EMAIL", "")
        self.password = password or os.getenv("YAZIO_PASSWORD", "")
        self.token = os.getenv("YAZIO_TOKEN", "")
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from yazio_exporter.client import YazioClient
            from yazio_exporter.auth import load_token, login_and_save

            self.client = YazioClient()

            # 1. Try reading from token file or env
            if not self.token and YAZIO_TOKEN_FILE.exists():
                with open(YAZIO_TOKEN_FILE, "r", encoding="utf-8") as f:
                    self.token = f.read().strip()

            if self.token:
                self.client.set_token(self.token)
                return

            # 2. Try logging in if credentials exist
            if self.email and self.password:
                token = login_and_save(self.email, self.password, str(YAZIO_TOKEN_FILE))
                self.token = token
                self.client.set_token(token)
        except Exception as e:
            # Client will stay unauthenticated until credentials provided
            pass

    def is_configured(self) -> bool:
        return bool(self.token or (self.email and self.password))

    def authenticate(self, email: str, password: str) -> bool:
        """Authenticates with YAZIO and caches the token."""
        try:
            from yazio_exporter.client import YazioClient
            from yazio_exporter.auth import login_and_save

            self.email = email
            self.password = password
            self.client = YazioClient()
            token = login_and_save(email, password, str(YAZIO_TOKEN_FILE))
            self.token = token
            self.client.set_token(token)
            return True
        except Exception as e:
            raise RuntimeError(f"Ошибка авторизации в YAZIO: {e}")

    def get_user_profile(self) -> Dict[str, Any]:
        """Fetches personal metrics (weight, height, age, goal) from YAZIO."""
        if not self.client or not self.token:
            raise RuntimeError("YAZIO не авторизован.")

        from yazio_exporter.export_profile import fetch_user
        from yazio_exporter.export_body import fetch_weight_range
        from datetime import date, timedelta, datetime

        user = fetch_user(self.client) or {}
        
        # Calculate age
        dob_str = user.get("date_of_birth")
        age = 0
        if dob_str:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        # Fetch recent weight
        start_d = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_d = date.today().strftime("%Y-%m-%d")
        weights = fetch_weight_range(self.client, start_d, end_d)
        
        latest_weight = user.get("start_weight", 0.0)
        if weights:
            latest_date = max(weights.keys())
            latest_weight = round(weights[latest_date], 1)

        start_weight = user.get("start_weight", latest_weight)

        return {
            "sex": user.get("sex", "male"),
            "height_cm": int(user.get("body_height", 182)),
            "age": age,
            "current_weight_kg": latest_weight,
            "start_weight_kg": start_weight,
            "weight_change_kg": round(latest_weight - start_weight, 1),
            "goal": user.get("goal", "lose"),
            "activity_degree": user.get("activity_degree", "high")
        }

    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Fetches calories and macronutrient breakdown for a given date as a clean dict."""
        if not self.client or not self.token:
            raise RuntimeError("YAZIO не авторизован. Укажите логин и пароль.")

        d = target_date or date.today()
        from yazio_exporter.export_days import fetch_daily_summary

        try:
            summary = fetch_daily_summary(self.client, d)
            if not summary:
                return {}

            total_cal = 0.0
            total_prot = 0.0
            total_fat = 0.0
            total_carb = 0.0
            meals_dict = {}

            meal_names_ru = {
                "breakfast": "Завтрак",
                "lunch": "Обед",
                "dinner": "Ужин",
                "snack": "Перекус"
            }

            for m_key, m_val in getattr(summary, "meals", {}).items():
                nut = m_val.get("nutrients", {})
                m_cal = float(nut.get("energy.energy", 0.0))
                m_prot = float(nut.get("nutrient.protein", 0.0))
                m_fat = float(nut.get("nutrient.fat", 0.0))
                m_carb = float(nut.get("nutrient.carb", 0.0))

                total_cal += m_cal
                total_prot += m_prot
                total_fat += m_fat
                total_carb += m_carb

                if m_cal > 0 or m_prot > 0:
                    meals_dict[meal_names_ru.get(m_key, m_key)] = {
                        "calories": round(m_cal, 1),
                        "protein": round(m_prot, 1),
                        "fat": round(m_fat, 1),
                        "carbs": round(m_carb, 1)
                    }

            goals = getattr(summary, "goals", {}) or {}

            return {
                "date": d.strftime("%d.%m.%Y"),
                "calories": round(total_cal, 1),
                "protein": round(total_prot, 1),
                "fat": round(total_fat, 1),
                "carbs": round(total_carb, 1),
                "water_ml": getattr(summary, "water_intake", 0),
                "steps": getattr(summary, "steps", 0),
                "goals": {
                    "calories": round(goals.get("energy.energy", 0), 1),
                    "protein": round(goals.get("nutrient.protein", 0), 1),
                    "fat": round(goals.get("nutrient.fat", 0), 1),
                    "carbs": round(goals.get("nutrient.carb", 0), 1),
                    "water_ml": goals.get("water", 0),
                    "steps": goals.get("activity.step", 0),
                    "weight_kg": goals.get("bodyvalue.weight", 0)
                },
                "meals": meals_dict
            }
        except Exception as e:
            raise RuntimeError(f"Не удалось получить данные из YAZIO за {d}: {e}")

    def get_recent_days(self, days_count: int = 3) -> List[Dict[str, Any]]:
        """Fetches recent nutrition summaries."""
        if not self.client or not self.token:
            return []

        from datetime import timedelta
        results = []
        today = date.today()
        for i in range(days_count):
            cur_date = today - timedelta(days=i)
            try:
                data = self.get_daily_summary(cur_date)
                if data:
                    results.append({"date": cur_date.strftime("%Y-%m-%d"), "summary": data})
            except Exception:
                continue
        return results
