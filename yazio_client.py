import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from config import BASE_DIR, DATA_DIR

YAZIO_TOKEN_FILE = DATA_DIR / "yazio_token.txt"
NUTRITION_CACHE_FILE = DATA_DIR / "nutrition_cache.json"
PRODUCTS_CACHE_FILE = DATA_DIR / "products_cache.json"

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

    def _execute_with_retry(self, func, *args, **kwargs):
        """Executes a function, auto-refreshing authentication on 401 Unauthorized errors."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if ("401" in err_msg or "unauthorized" in err_msg or "token" in err_msg) and self.email and self.password:
                print("🔄 YAZIO токен истек, выполняю автоматический повторный вход...")
                try:
                    self.authenticate(self.email, self.password)
                    return func(*args, **kwargs)
                except Exception as auth_err:
                    print(f"Ошибка повторной авторизации YAZIO: {auth_err}")
            raise

    def get_user_profile(self) -> Dict[str, Any]:
        """Fetches personal metrics (weight, height, age, goal) from YAZIO."""
        if not self.client or not self.token:
            if self.email and self.password:
                self.authenticate(self.email, self.password)
            else:
                raise RuntimeError("YAZIO не авторизован.")

        try:
            from yazio_exporter.export_profile import fetch_user
            from yazio_exporter.export_body import fetch_weight_range

            user = self._execute_with_retry(fetch_user, self.client) or {}

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
            weights = self._execute_with_retry(fetch_weight_range, self.client, start_d, end_d)

            latest_weight = user.get("start_weight", 97.9)
            if weights:
                latest_date = max(weights.keys())
                latest_weight = round(weights[latest_date], 1)

            start_weight = user.get("start_weight", 103.0)

            return {
                "sex": user.get("sex", "male"),
                "height_cm": int(user.get("body_height", 182)),
                "age": age or 22,
                "current_weight_kg": latest_weight,
                "start_weight_kg": start_weight,
                "weight_change_kg": round(latest_weight - start_weight, 1),
                "goal": user.get("goal", "lose"),
                "activity_degree": user.get("activity_degree", "high")
            }
        except Exception as e:
            print(f"Error fetching YAZIO user profile ({e}), using safe fallback values...")
            return {
                "sex": "male",
                "height_cm": 182,
                "age": 22,
                "current_weight_kg": 97.9,
                "start_weight_kg": 103.0,
                "weight_change_kg": -5.1,
                "goal": "lose",
                "activity_degree": "high"
            }

    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Fetches calories and macronutrient breakdown for a given date as a clean dict."""
        if not self.client or not self.token:
            if self.email and self.password:
                self.authenticate(self.email, self.password)
            else:
                return {}

        d = target_date or date.today()
        from yazio_exporter.export_days import fetch_daily_summary

        try:
            summary = self._execute_with_retry(fetch_daily_summary, self.client, d)
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
                "raw_date": d.strftime("%Y-%m-%d"),
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

    def _load_products_cache(self) -> Dict[str, Any]:
        if PRODUCTS_CACHE_FILE.exists():
            try:
                with open(PRODUCTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_products_cache(self, cache: Dict[str, Any]):
        try:
            with open(PRODUCTS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

    def get_consumed_products(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Fetches detailed list of consumed foods and products for a given date with local caching."""
        if not self.client or not self.token:
            if self.email and self.password:
                self.authenticate(self.email, self.password)
            else:
                raise RuntimeError("YAZIO не авторизован.")

        from yazio_exporter.export_days import fetch_consumed
        from yazio_exporter.export_products import fetch_product

        d = target_date or date.today()
        consumed = self._execute_with_retry(fetch_consumed, self.client, d)
        if not consumed or not getattr(consumed, "products", None):
            return {"date": d.strftime("%d.%m.%Y"), "meals": {}}

        cache = self._load_products_cache()
        cache_updated = False

        meal_names_ru = {
            "breakfast": "Завтрак",
            "lunch": "Обед",
            "dinner": "Ужин",
            "snack": "Перекус"
        }

        meals_dict = {
            "Завтрак": [],
            "Обед": [],
            "Ужин": [],
            "Перекус": []
        }

        for item in consumed.products:
            pid = item.get("product_id")
            amount = item.get("amount", 0)
            daytime = item.get("daytime", "snack")
            meal_key = meal_names_ru.get(daytime, "Перекус")

            prod_info = cache.get(pid)
            if not prod_info:
                try:
                    prod_info = fetch_product(self.client, pid)
                    if prod_info:
                        cache[pid] = prod_info
                        cache_updated = True
                except Exception:
                    prod_info = {"name": "Продукт"}

            name = prod_info.get("name", "Продукт") if prod_info else "Продукт"
            producer = prod_info.get("producer") if prod_info else None

            # Approximate calories if available
            nut = prod_info.get("nutrients", {}) if prod_info else {}
            cal_per_g = float(nut.get("energy.energy", 0.0))
            cal = round(amount * cal_per_g) if cal_per_g > 0 else None

            meals_dict[meal_key].append({
                "name": name,
                "producer": producer,
                "amount_g": amount,
                "calories": cal
            })

        if cache_updated:
            self._save_products_cache(cache)

        filtered_meals = {k: v for k, v in meals_dict.items() if v}

        return {
            "date": d.strftime("%d.%m.%Y"),
            "meals": filtered_meals
        }

    def get_weekly_nutrition(self, days_count: int = 7) -> Dict[str, Any]:
        """Fetches daily nutrition summaries for the past N days and calculates averages."""
        if not self.client or not self.token:
            raise RuntimeError("YAZIO не авторизован.")

        today = date.today()
        weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        days_list = []
        total_cal = 0.0
        total_prot = 0.0
        total_fat = 0.0
        total_carb = 0.0
        logged_days = 0

        for i in range(days_count - 1, -1, -1):
            cur_date = today - timedelta(days=i)
            try:
                summary = self.get_daily_summary(cur_date)
                cal = summary.get("calories", 0.0)
                prot = summary.get("protein", 0.0)
                fat = summary.get("fat", 0.0)
                carb = summary.get("carbs", 0.0)

                is_logged = (cal > 0 or prot > 0)
                if is_logged:
                    total_cal += cal
                    total_prot += prot
                    total_fat += fat
                    total_carb += carb
                    logged_days += 1

                days_list.append({
                    "date": cur_date.strftime("%d.%m"),
                    "full_date": cur_date.strftime("%d.%m.%Y"),
                    "weekday": weekday_names[cur_date.weekday()],
                    "calories": round(cal),
                    "protein": round(prot, 1),
                    "fat": round(fat, 1),
                    "carbs": round(carb, 1),
                    "is_today": (cur_date == today),
                    "is_logged": is_logged
                })
            except Exception:
                continue

        avg_cal = round(total_cal / logged_days) if logged_days > 0 else 0
        avg_prot = round(total_prot / logged_days, 1) if logged_days > 0 else 0
        avg_fat = round(total_fat / logged_days, 1) if logged_days > 0 else 0
        avg_carb = round(total_carb / logged_days, 1) if logged_days > 0 else 0

        return {
            "start_date": (today - timedelta(days=days_count - 1)).strftime("%d.%m"),
            "end_date": today.strftime("%d.%m"),
            "days": days_list,
            "logged_days_count": logged_days,
            "avg_calories": avg_cal,
            "avg_protein": avg_prot,
            "avg_fat": avg_fat,
            "avg_carbs": avg_carb,
            "total_calories": round(total_cal)
        }
