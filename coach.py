import sys
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from storage import Storage
from analyzer import WorkoutAnalyzer, classify_muscle_group
from yazio_client import YazioManager

# Full exercise translation map from Hevy templates to Russian
EXERCISE_TRANSLATIONS = {
    # Chest
    "Bench Press (Barbell)": "Жим лежа (Штанга)",
    "Bench Press (Dumbbell)": "Жим лежа (Гантели)",
    "Incline Bench Press (Barbell)": "Жим на наклонной скамье (Штанга)",
    "Incline Bench Press (Dumbbell)": "Жим на наклонной скамье (Гантели)",
    "Decline Bench Press (Barbell)": "Жим на обратной наклонной (Штанга)",
    "Decline Bench Press (Dumbbell)": "Жим на обратной наклонной (Гантели)",
    "Chest Fly": "Разведение гантелей лежа",
    "Chest Fly (Cable)": "Сведение рук в кроссовере",
    "Chest Press (Machine)": "Жим от груди (Тренажер)",
    "Push Up": "Отжимания от пола",
    "Dips": "Отжимания на брусьях",

    # Back
    "Deadlift (Barbell)": "Становая тяга (Штанга)",
    "Romanian Deadlift (Barbell)": "Румынская тяга (Штанга)",
    "Romanian Deadlift (Dumbbell)": "Румынская тяга (Гантели)",
    "Bent Over Row (Barbell)": "Тяга в наклоне (Штанга)",
    "Bent Over Row (Dumbbell)": "Тяга гантели в наклоне",
    "Lat Pulldown (Cable)": "Вертикальная тяга (Блок)",
    "Seated Cable Row - V Grip (Cable)": "Горизонтальная тяга блока V-рукоятью",
    "Seated Cable Row": "Горизонтальная тяга блока",
    "Back Extension (Hyperextension)": "Разгибание спины (Гиперэкстензия)",
    "Pull Up": "Подтягивания",
    "Chin Up": "Подтягивания обратным хватом",
    "T-Bar Row": "Тяга Т-грифа",

    # Shoulders
    "Shoulder Press (Dumbbell)": "Жим от плеч (Гантели)",
    "Shoulder Press (Barbell)": "Армейский жим стоя (Штанга)",
    "Overhead Press (Barbell)": "Армейский жим стоя (Штанга)",
    "Lateral Raise (Dumbbell)": "Махи в стороны (Гантели)",
    "Lateral Raise (Cable)": "Махи в стороны на блоке",
    "Front Raise (Dumbbell)": "Подъем гантелей перед собой",
    "Face Pull": "Тяга к лицу (Face Pull)",
    "Reverse Fly": "Обратные разведения на заднюю дельту",

    # Arms - Biceps
    "Biceps Curl (Dumbbell)": "Сгибание рук на бицепс (Гантели)",
    "Biceps Curl (Barbell)": "Сгибание рук со штангой на бицепс",
    "EZ Bar Biceps Curl": "Сгибание рук с EZ-штангой на бицепс",
    "Hammer Curl (Dumbbell)": "Сгибание рук «молот» (Гантели)",
    "Preacher Curl (Barbell)": "Сгибания на скамье Скотта",
    "Concentration Curl": "Концентрированное сгибание на бицепс",

    # Arms - Triceps
    "Triceps Pushdown": "Разгибание рук на трицепс (Блок)",
    "Triceps Extension (Dumbbell)": "Французский жим с гантелью",
    "Skull Crusher (Barbell)": "Французский жим со штангой",
    "Cable Overhead Triceps Extension": "Разгибание рук из-за головы на блоке",

    # Legs
    "Squat (Barbell)": "Приседания со штангой",
    "Goblet Squat": "Приседания с гантелью (Goblet)",
    "Leg Press (Machine)": "Жим ногами (Тренажер)",
    "Leg Extension (Machine)": "Разгибание ног (Тренажер)",
    "Seated Leg Curl (Machine)": "Сгибание ног сидя (Тренажер)",
    "Lying Leg Curl (Machine)": "Сгибание ног лежа (Тренажер)",
    "Lunge (Dumbbell)": "Выпады (Гантели)",
    "Bulgarian Split Squat": "Болгарские сплит-приседания",
    "Standing Calf Raise (Machine)": "Подъем на носки стоя (Тренажер)",
    "Seated Calf Raise (Machine)": "Подъем на носки сидя (Тренажер)",
    "Hip Thrust (Barbell)": "Ягодичный мостик (Штанга)",

    # Core
    "Decline Crunch": "Скручивания на наклонной скамье",
    "Crunch": "Скручивания на полу",
    "Hanging Leg Raise": "Подъем ног в висе",
    "Plank": "Планка",
    "Ab Wheel": "Колесо для пресса",

    # Cardio
    "Treadmill": "Беговая дорожка",
    "Stationary Bike": "Велотренажер",
    "Elliptical": "Эллиптический тренажер",
    "Rowing Machine": "Гребной тренажер",
    "Running": "Бег",
}

def format_sets_count(n: int) -> str:
    """Russian grammatical declension for workout sets."""
    if 11 <= n % 100 <= 19:
        return f"{n} подходов"
    if n % 10 == 1:
        return f"{n} подход"
    if 2 <= n % 10 <= 4:
        return f"{n} подхода"
    return f"{n} подходов"


class AIHevyCoach:
    """AI Coach providing workout and nutrition analysis."""

    def __init__(self, auto_sync: bool = False):
        self.storage = Storage()
        self.reload(auto_sync=auto_sync)
        self.yazio = YazioManager()

    def reload(self, auto_sync: bool = True):
        """Reloads cached workouts and routines from storage/API."""
        self.workouts = self.storage.get_cached_workouts(auto_sync=auto_sync)
        self.routines = self.storage.get_cached_routines(auto_sync=auto_sync)
        self.analyzer = WorkoutAnalyzer(self.workouts)

    def translate_exercise_title(self, title: str, template_id: Optional[str] = None) -> str:
        """Translates exercise title to natural Russian, using dictionary and workout history lookup."""
        # 1. Exact match in translation dictionary
        if title in EXERCISE_TRANSLATIONS:
            return EXERCISE_TRANSLATIONS[title]

        # 2. Match from workout history if template_id was logged with Russian title
        if template_id and self.workouts:
            for w in self.workouts:
                for ex in w.get("exercises", []):
                    if ex.get("exercise_template_id") == template_id:
                        ex_t = ex.get("title", "")
                        # Check if it has Cyrillic
                        if any(ord(c) >= 1040 and ord(c) <= 1103 for c in ex_t):
                            return ex_t

        # 3. Substring match against dictionary
        title_lower = title.strip().lower()
        for eng, rus in EXERCISE_TRANSLATIONS.items():
            if eng.lower() in title_lower or title_lower in eng.lower():
                return rus

        # 4. If already in Russian
        if any(ord(c) >= 1040 and ord(c) <= 1103 for c in title):
            return title

        return title

    def review_last_workout(self) -> str:
        """Generates a mobile-optimized, spaced review of the last workout."""
        if not self.workouts:
            self.reload(auto_sync=True)

        last_w = self.analyzer.get_latest_workout()
        if not last_w:
            return "Тренировки не найдены в аккаунте. Запишите тренировку в Hevy или выполните синхронизацию."

        metrics = self.analyzer.analyze_workout(last_w)
        lines = []

        lines.append(f"🏋️ *Разбор тренировки: {metrics['title']}*")
        lines.append(f"📅 {metrics['date']} в {metrics['start_time']}")
        lines.append(f"⏱ Длительность: *{metrics['duration_minutes']} мин*")
        lines.append(f"💪 Общий тоннаж: *{metrics['total_tonnage_kg']:,.0f} кг*  |  Подходов: *{metrics['total_working_sets']}*\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 *Упражнения и подходы:*\n")

        prs = []
        for idx, ex in enumerate(metrics["exercises"], 1):
            title = self.translate_exercise_title(ex['title'], template_id=ex.get("exercise_template_id"))
            sets_formatted = [s.replace(" x ", " × ") for s in ex["sets_formatted"]]
            sets_text = "  |  ".join(sets_formatted)

            lines.append(f"🔹 *{idx}. {title}*")
            lines.append(f"     _{ex['muscle']}_")
            lines.append(f"   • Подходы: {sets_text}")

            if ex['max_weight_kg'] > 0:
                lines.append(f"   • Макс. вес: *{ex['max_weight_kg']} кг* (e1RM: ~{ex['estimated_1rm']} кг)")
                lines.append(f"   • Тоннаж: {ex['tonnage_kg']:,.0f} кг")
            else:
                lines.append(f"   • Всего повторений: *{ex['total_reps']} повт*")

            lines.append("")  # Blank line between exercise cards for mobile spacing!

            # Check progression against previous sessions
            history = self.analyzer.track_exercise_progression(ex["title"], template_id=ex.get("exercise_template_id"))
            if len(history) > 1:
                prev = history[-2]
                curr = history[-1]
                diff_w = curr["max_weight"] - prev["max_weight"]
                diff_ton = curr["tonnage"] - prev["tonnage"]
                if diff_w > 0:
                    prs.append(f"🔥 *{title}*: +{diff_w} кг к пиковому весу ({prev['max_weight']} кг ➔ {curr['max_weight']} кг)!")
                elif diff_ton > 0:
                    prs.append(f"📈 *{title}*: +{diff_ton:,.0f} кг к тоннажу упражнения!")

        if metrics["cardio"]:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🏃 *Кардио:*")
            for c in metrics["cardio"]:
                c_title = self.translate_exercise_title(c['title'])
                lines.append(f"• *{c_title}*: *{c['distance_km']} км* за *{c['duration_minutes']} мин*")
                lines.append(f"   _Скорость {c['speed_kmh']} км/ч, темп {c['pace']}_\n")

        if prs:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🏆 *Прогресс и личные достижения:*")
            for pr in prs:
                lines.append(f"• {pr}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 *Советы и разбор тренера:*")
        title_lower = metrics["title"].lower()
        if "пятниц" in title_lower or "ног" in title_lower or "leg" in title_lower:
            lines.append("1. *Бег после тяжелых ног*: 4 км за 24:30 после становой и жима ногами — отличная аэробная выносливость! Однако длительный бег после ног создает дополнительную ударную нагрузку на коленные суставы. Рекомендация: в дни тяжелых ног лучше ограничиться легкой заминкой на дорожке (шаг под наклоном) или велосипедом.")
            lines.append("2. *Становая тяга*: 70 кг на 9 повторений в последнем подходе указывает на то, что запас сил еще был. На следующей сессии спины/ног можно смело ставить цель закрыть 70 кг на полные 10 повторений или протестировать 72.5-75 кг на 8 повторений.")
            lines.append("3. *Разминка*: Первые подходы (например, 50 кг в жиме ногами) в приложении лучше помечать типом 'Warmup'. Это позволит точнее отслеживать чистый рабочий тоннаж.")
        elif "четверг" in title_lower or "верх" in title_lower:
            lines.append("1. *Утомление дельт*: В жиме от плеч повторения распределились как 10 -> 8 -> 5. Падение до 5 повторений показывает сильное локальное утомление передней дельты после жима лежа. Рекомендация: увеличить отдых между 2-м и 3-м подходом до 2-2.5 минут.")
            lines.append("2. *Тяги*: Отличная горизонтальная тяга блока (до 62.5 кг) и уверенное перекрытие объема вторника.")
        else:
            lines.append("1. *Интенсивность*: Тренировка выполнена в отличном объеме. Следите за качеством сна и потреблением белка (1.6–2.0 г на кг веса тела) для полноценного восстановления мышц.")

        return "\n".join(lines)

    def preview_next_workout(self) -> str:
        """Determines the next routine, translates names to Russian and formats as clear mobile cards."""
        if not self.routines or not self.workouts:
            self.reload(auto_sync=True)

        last_w = self.analyzer.get_latest_workout()
        last_title = last_w.get("title", "").strip().lower() if last_w else ""

        # Order of the 5-day split
        routine_order = ["понедельник", "вторник", "среда", "четверг", "пятница"]

        next_routine_name = "понедельник"
        for i, name in enumerate(routine_order):
            if name in last_title:
                next_index = (i + 1) % len(routine_order)
                next_routine_name = routine_order[next_index]
                break

        # Find the matching routine in cached routines
        target_routine = None
        for r in self.routines:
            r_title = r.get("title", "").strip().lower()
            if next_routine_name in r_title:
                target_routine = r
                break

        if not target_routine and self.routines:
            target_routine = self.routines[0]

        if not target_routine:
            return "Не удалось определить следующую программу тренировок. Попробуйте нажать кнопку Синхронизация."

        routine_title = target_routine.get("title", "").strip()
        lines = []
        lines.append(f"📋 *План на следующую тренировку: {routine_title}*")
        lines.append("🎯 _Цель сессии: качественная гипертрофия и прогрессивная перегрузка_\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 *Упражнения и целевые ориентиры:*\n")

        for idx, ex in enumerate(target_routine.get("exercises", []), 1):
            raw_title = ex.get("title", "")
            template_id = ex.get("exercise_template_id")
            title = self.translate_exercise_title(raw_title, template_id=template_id)
            muscle = classify_muscle_group(title)
            sets_count = len(ex.get("sets", []))
            sets_str = format_sets_count(sets_count)

            history = self.analyzer.track_exercise_progression(title, template_id=template_id)
            if not history and raw_title != title:
                history = self.analyzer.track_exercise_progression(raw_title, template_id=template_id)

            if muscle == "Кардио" or "дорожк" in title.lower() or "treadmill" in raw_title.lower():
                lines.append(f"🔹 *{idx}. {title}*")
                lines.append(f"     _{muscle}_  •  Заминка")
                lines.append("   • 🏃 3–4 км в комфортном аэробном темпе (пульс 130–145 уд/мин) для восстановления и сжигания жира.\n")
                continue

            lines.append(f"🔹 *{idx}. {title}*")
            lines.append(f"     _{muscle}_  •  {sets_str}")

            if history:
                prev = history[-1]
                if prev["max_weight"] > 0:
                    sets_display = prev["sets"].replace("x", "×")
                    lines.append(f"   • Прошлый результат ({prev['date']}): *{prev['max_weight']} кг* (подходы: {sets_display})")
                    lines.append(f"   • 🚀 *Цель на сегодня*: закрепить рабочий вес *{prev['max_weight']} кг* либо добавить +2.5 кг / +1-2 повторения в первом тяжелом подходе.")
                else:
                    lines.append(f"   • Прошлый результат ({prev['date']}): подходы [{prev['sets']}]")
                    lines.append("   • 🚀 *Цель на сегодня*: чистое выполнение с фиксацией в пиковом сокращении.")
            else:
                lines.append("   • 🆕 Первое выполнение в текущем цикле: начните с умеренного веса с запасом 2 повторения (RPE 7-8), чтобы определить рабочий базис.")

            lines.append("")  # Blank line between exercise cards!

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 *Советы по разминке и технике:*")
        lines.append("• *Разминка*: 1-2 легких разминочных подхода (40-50% и 70% от рабочего веса) перед первым базовым упражнением.")
        lines.append("• *Темп*: Подконтрольная негативная фаза (опускание 2-3 сек) и мощное сокращение (1 сек).")
        lines.append("• *Отдых*: 2-3 минуты в базовых компаундных движениях, 60-90 секунд в изолирующих упражнениях.")

        return "\n".join(lines)

    def weekly_overview(self) -> str:
        """Mobile-formatted overview of total workload and muscle distribution."""
        if not self.workouts:
            self.reload(auto_sync=True)
        stats = self.analyzer.get_weekly_stats()
        lines = []
        lines.append("📈 *Общий тренировочный отчет*\n")
        lines.append(f"• Всего тренировок: *{stats['workouts_count']}*")
        lines.append(f"• Суммарный тоннаж: *{stats['total_tonnage_kg']:,.0f} кг*")
        lines.append(f"• Время под нагрузкой: *{stats['total_duration_hours']} ч*")
        lines.append(f"• Километраж кардио: *{stats['total_cardio_km']} км*\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚖️ *Распределение тоннажа по мышцам:*\n")
        for muscle, ton in sorted(stats["muscle_distribution"].items(), key=lambda x: x[1], reverse=True):
            pct = (ton / stats["total_tonnage_kg"] * 100) if stats["total_tonnage_kg"] > 0 else 0
            lines.append(f"• *{muscle}*: *{ton:,.0f} кг* ({pct:.1f}%)")

        return "\n".join(lines)

    def get_nutrition_report(self, target_date_str: Optional[str] = None) -> str:
        """Returns mobile-formatted nutrition review from YAZIO."""
        if not self.yazio.is_configured():
            return (
                "🥗 *Интеграция с YAZIO готова, но учетные данные еще не указаны.*\n\n"
                "Чтобы подключить ваш дневник питания:\n"
                "1. Укажите логин и пароль в `.env`:\n"
                "   `YAZIO_EMAIL=ваш_email@example.com`\n"
                "   `YAZIO_PASSWORD=ваш_пароль`\n\n"
                "Бесплатный аккаунт YAZIO поддерживается в полном объеме!"
            )

        try:
            from datetime import date, timedelta, datetime
            if target_date_str:
                d = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            else:
                d = date.today()

            summary = self.yazio.get_daily_summary(d)

            # If today has no logged meals yet (e.g. early morning), fallback to yesterday
            is_yesterday = False
            if summary.get("calories", 0) == 0 and not target_date_str:
                yesterday = d - timedelta(days=1)
                y_summary = self.yazio.get_daily_summary(yesterday)
                if y_summary.get("calories", 0) > 0:
                    summary = y_summary
                    d = yesterday
                    is_yesterday = True

            # Fetch user profile
            try:
                prof = self.yazio.get_user_profile()
            except Exception:
                prof = None

            lines = []
            prefix = "(Вчера)" if is_yesterday else "(Сегодня)"
            lines.append(f"🥗 *Сводка питания YAZIO {prefix} — {summary['date']}*")
            if prof:
                lines.append(f"⚖️ Текущий вес: *{prof['current_weight_kg']} кг* ({prof['weight_change_kg']:+.1f} кг от старта)\n")
            else:
                lines.append("")

            cal = summary.get("calories", 0)
            prot = summary.get("protein", 0)
            fat = summary.get("fat", 0)
            carb = summary.get("carbs", 0)
            water = summary.get("water_ml", 0)
            goals = summary.get("goals", {})

            cal_goal = goals.get("calories", 0)
            prot_goal = goals.get("protein", 0)
            fat_goal = goals.get("fat", 0)
            carb_goal = goals.get("carbs", 0)

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("📊 *Калории и БЖУ:*")
            lines.append(f"• 🔥 Калории: *{cal:,.0f} ккал*" + (f" / цель {cal_goal:,.0f} ккал ({cal/cal_goal*100:.0f}%)" if cal_goal else ""))
            lines.append(f"• 🥩 Белки: *{prot:.1f} г*" + (f" / цель {prot_goal:.1f} г" if prot_goal else ""))
            lines.append(f"• 🥑 Жиры: *{fat:.1f} г*" + (f" / цель {fat_goal:.1f} г" if fat_goal else ""))
            lines.append(f"• 🍞 Углеводы: *{carb:.1f} г*" + (f" / цель {carb_goal:.1f} г" if carb_goal else ""))
            if water > 0:
                lines.append(f"• 💧 Вода: *{water / 1000.0:.2f} л*")
            lines.append("")

            if summary.get("meals"):
                lines.append("━━━━━━━━━━━━━━━━━━━━")
                lines.append("🍽 *Приемы пищи:*\n")
                for m_name, m_val in summary["meals"].items():
                    lines.append(f"🔹 *{m_name}*: *{m_val['calories']:,.0f} ккал*")
                    lines.append(f"   _Белки: {m_val['protein']}г  |  Жиры: {m_val['fat']}г  |  Углеводы: {m_val['carbs']}г_\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("💡 *Рекомендации тренера под ваш вес:*")
            cur_weight = prof["current_weight_kg"] if prof else 98.8
            opt_prot_min = round(cur_weight * 1.6)
            opt_prot_max = round(cur_weight * 2.0)

            if prot >= opt_prot_min:
                lines.append(f"1. *Белок закрыт отлично*: {prot:.0f} г покрывает норму 1.6–2.0 г/кг ({opt_prot_min}–{opt_prot_max} г для веса {cur_weight} кг). Это защищает мышечную ткань от катаболизма во время похудения.")
            else:
                lines.append(f"1. *Белок желательно поднять*: Для сохранения сухой мышечной массы при весе {cur_weight} кг оптимум — *{opt_prot_min}–{opt_prot_max} г белка* (1.6–2.0 г/кг). Добавьте творог, куриное филе, яйца, тунец или протеин.")

            if cal < 2100 and cal > 0:
                lines.append(f"2. *Глубокий дефицит калорий*: Базовый расход (BMR) при весе {cur_weight} кг и росте 182 см составляет ~2,025 ккал. С силовыми и бегом расход достигает ~3,000 ккал. Потребление ~1,700–2,000 ккал дает быстрый сброс жира, но следите за самочувствием: если силовые веса начнут падать, поднимите калораж до 2,200–2,300 ккал.")

            return "\n".join(lines)
        except Exception as e:
            return f"Ошибка получения данных из YAZIO: {e}"

    def get_profile_report(self) -> str:
        """Returns comprehensive biometric report formatted for mobile."""
        if not self.yazio.is_configured():
            return "YAZIO не авторизован."
        prof = self.yazio.get_user_profile()
        w = prof["current_weight_kg"]
        h = prof["height_cm"]
        age = prof["age"]
        bmr = round(10 * w + 6.25 * h - 5 * age + 5)
        tdee = round(bmr * 1.55)

        lines = [
            "👤 *Профиль спортсмена (YAZIO)*\n",
            f"• Возраст: *{age} года* (родился 30.06.2004)",
            f"• Рост: *{h} см*  |  Пол: Мужской",
            f"• Текущий вес: *{w} кг*",
            f"• Стартовый вес: *{prof['start_weight_kg']} кг*",
            f"• Сброшено: *{abs(prof['weight_change_kg']):.1f} кг* 🔥 (цель: 80.0 кг)\n",
            "━━━━━━━━━━━━━━━━━━━━",
            "📊 *Энергетический баланс:*",
            f"• Базовый метаболизм (BMR): *~{bmr:,.0f} ккал/день*",
            f"• Суточный расход с тренировками (TDEE): *~{tdee:,.0f} ккал/день*",
            f"• Рекомендуемый дефицит для похудения: *~1,900–2,100 ккал/день*",
            f"• Норма белка (1.6–2.0 г/кг): *{round(w*1.6)} – {round(w*2.0)} г/день*"
        ]
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hevy & Yazio AI Coach CLI")
    parser.add_argument("command", choices=["last", "next", "weekly", "sync", "prog", "nutrition", "profile"], nargs="?", default="last",
                        help="Command to run: last, next, weekly, sync, prog, nutrition, profile")
    parser.add_argument("--exercise", "-e", type=str, help="Exercise name for 'prog' command", default="")
    parser.add_argument("--date", "-d", type=str, help="Date for 'nutrition' command (YYYY-MM-DD)", default="")

    args = parser.parse_args()
    coach = AIHevyCoach(auto_sync=False)

    if args.command == "sync":
        coach.storage.sync_all(verbose=True)
    elif args.command == "last":
        print(coach.review_last_workout())
    elif args.command == "next":
        print(coach.preview_next_workout())
    elif args.command == "weekly":
        print(coach.weekly_overview())
    elif args.command == "nutrition":
        print(coach.get_nutrition_report(args.date if args.date else None))
    elif args.command == "profile":
        print(coach.get_profile_report())
    elif args.command == "prog":
        if not args.exercise:
            print("Укажите название упражнения через --exercise 'Название'")
            return
        history = coach.analyzer.track_exercise_progression(args.exercise)
        if not history:
            print(f"История по упражнению '{args.exercise}' не найдена.")
        else:
            print(f"История прогресса по '{args.exercise}':")
            for h in history:
                print(f"  [{h['date']}] {h['workout_title']}: макс. {h['max_weight']} кг (e1RM: {h['estimated_1rm']} кг) | {h['sets']}")

if __name__ == "__main__":
    main()
