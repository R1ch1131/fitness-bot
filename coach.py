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
        self.hevy = self.storage.client
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

    def get_weekly_nutrition_report(self) -> str:
        """Generates a mobile-optimized weekly nutrition summary with daily breakdown and averages."""
        if not self.yazio.is_configured():
            return "YAZIO не авторизован."

        try:
            weekly = self.yazio.get_weekly_nutrition(days_count=7)
            if not weekly or not weekly.get("days"):
                return "Не удалось получить данные о питании за неделю."

            lines = []
            lines.append("🥗 *Недельный отчет по питанию (YAZIO)*")
            lines.append(f"📅 Период: *с {weekly['start_date']} по {weekly['end_date']}* (за 7 дней)\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("📊 *Среднесуточные показатели:*")
            lines.append(f"• 🔥 Средний калораж: *{weekly['avg_calories']:,} ккал/день*")
            lines.append(f"• 🥩 Средний белок: *{weekly['avg_protein']} г/день* (цель: 158–198 г)")
            lines.append(f"• 🥑 Средние жиры: *{weekly['avg_fat']} г/день*")
            lines.append(f"• 🍞 Средние углеводы: *{weekly['avg_carbs']} г/день*\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("📅 *По дням недели:*\n")

            for d in weekly["days"]:
                tag = " _(сегодня)_" if d.get("is_today") else ""
                if d.get("is_logged"):
                    lines.append(f"• *{d['date']} ({d['weekday']})*{tag}: *{d['calories']:,} ккал*")
                    lines.append(f"   _Б: {d['protein']}г  |  Ж: {d['fat']}г  |  У: {d['carbs']}г_\n")
                else:
                    lines.append(f"• *{d['date']} ({d['weekday']})*{tag}: _нет записей_\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("💡 *Оценка тренера:*")
            cur_weight = 98.8
            try:
                prof = self.yazio.get_user_profile()
                cur_weight = prof.get("current_weight_kg", 98.8)
            except Exception:
                pass

            opt_prot = round(cur_weight * 1.6)
            if weekly['avg_protein'] >= opt_prot:
                lines.append(f"1. *Белок в норме*: средние {weekly['avg_protein']} г/день уверенно покрывают норму 1.6 г/кг для веса {cur_weight} кг. Мышцы надежно защищены от катаболизма!")
            else:
                lines.append(f"1. *Просадка по белку*: средние *{weekly['avg_protein']} г/день* ниже рекомендуемой планки *{opt_prot} г/день* (1.6 г/кг для веса {cur_weight} кг). Обратите внимание на дни с низким белком (<100 г) и добавьте творог, куриное филе, тунец или протеиновый коктейль.")

            if weekly['avg_calories'] > 0 and weekly['avg_calories'] < 2000:
                lines.append(f"2. *Качественный дефицит*: Средний калораж {weekly['avg_calories']:,} ккал/день создает отличный дефицит в ~1,000–1,200 ккал от расхода (TDEE ~3,100 ккал). При этом следите за самочувствием и силовыми весами в зале.")

            return "\n".join(lines)
        except Exception as e:
            return f"Ошибка при расчете недельного питания: {e}"

    def get_consumed_products_report(self, target_date_str: Optional[str] = None) -> str:
        """Returns detailed list of food products eaten for a given date."""
        if not self.yazio.is_configured():
            return "YAZIO не авторизован."

        try:
            from datetime import date, datetime, timedelta
            if target_date_str:
                d = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            else:
                d = date.today()

            data = self.yazio.get_consumed_products(d)

            # If today has no products yet (e.g. early morning), fallback to yesterday
            is_yesterday = False
            if not data.get("meals") and not target_date_str:
                yesterday = d - timedelta(days=1)
                y_data = self.yazio.get_consumed_products(yesterday)
                if y_data.get("meals"):
                    data = y_data
                    d = yesterday
                    is_yesterday = True

            prefix = "(Вчера)" if is_yesterday else "(Сегодня)"
            meals = data.get("meals", {})

            if not meals:
                return f"🍽 Записи о продуктах в YAZIO за {data.get('date', '')} не найдены."

            lines = []
            lines.append(f"🍽 *Продукты в рационе YAZIO {prefix} — {data['date']}*\n")

            meal_emojis = {
                "Завтрак": "🍳",
                "Обед": "🍲",
                "Ужин": "🥗",
                "Перекус": "🍏"
            }

            for meal_name, items in meals.items():
                emoji = meal_emojis.get(meal_name, "🍽")
                lines.append("━━━━━━━━━━━━━━━━━━━━")
                lines.append(f"{emoji} *{meal_name}:*\n")
                for item in items:
                    prod_name = item.get("name", "Продукт")
                    producer = f" ({item['producer']})" if item.get("producer") else ""
                    amount = f" — *{item['amount_g']} г*" if item.get("amount_g") else ""
                    cal_str = f" (~{item['calories']} ккал)" if item.get("calories") else ""
                    lines.append(f"• *{prod_name}*{producer}{amount}{cal_str}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"Ошибка при получении списка продуктов: {e}"

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

    def get_sunday_weekly_table_report(self, target_date=None) -> str:
        """Generates structured weekly Sunday summary with daily nutrition, workout tonnage, and weight dynamic."""
        from datetime import datetime, date, timedelta, timezone
        from analyzer import parse_iso

        tz_gmt6 = timezone(timedelta(hours=6))
        ref_date = target_date or datetime.now(tz_gmt6).date()

        # Monday of current week
        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)
        weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        # 1. Fetch weight range from YAZIO
        weight_history = {}
        if self.yazio.is_configured() and self.yazio.client:
            try:
                from yazio_exporter.export_body import fetch_weight_range
                w_start_str = (monday - timedelta(days=7)).strftime("%Y-%m-%d")
                w_end_str = (sunday + timedelta(days=1)).strftime("%Y-%m-%d")
                weight_history = self.yazio._execute_with_retry(
                    fetch_weight_range, self.yazio.client, w_start_str, w_end_str
                ) or {}
            except Exception as e:
                print(f"Weight history fetch note: {e}")

        # Map workouts by local date (GMT+6)
        workouts_by_date = {}
        for w in self.workouts:
            iso_start = w.get("start_time")
            if iso_start:
                try:
                    dt = parse_iso(iso_start)
                    if dt:
                        local_d = dt.astimezone(tz_gmt6).date()
                        workouts_by_date.setdefault(local_d, []).append(w)
                except Exception:
                    pass

        # 2. Collect daily data for Monday..Sunday
        daily_rows = []
        total_tonnage = 0.0
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        logged_days_count = 0
        workout_days_count = 0

        first_weight = None
        first_weight_date = None
        last_weight = None
        last_weight_date = None

        for i in range(7):
            day_d = monday + timedelta(days=i)
            day_str = day_d.strftime("%Y-%m-%d")
            w_name = weekday_names[i]
            day_label = f"{w_name} {day_d.strftime('%d')}"

            # Nutrition
            cal = 0
            prot = 0.0
            fat = 0.0
            carb = 0.0
            has_nut = False

            if self.yazio.is_configured() and day_d <= ref_date:
                try:
                    summary = self.yazio.get_daily_summary(day_d)
                    if summary:
                        cal = round(summary.get("calories", 0))
                        prot = round(summary.get("protein", 0), 1)
                        fat = round(summary.get("fat", 0), 1)
                        carb = round(summary.get("carbs", 0), 1)
                        if cal > 0 or prot > 0:
                            has_nut = True
                            total_calories += cal
                            total_protein += prot
                            total_fat += fat
                            total_carbs += carb
                            logged_days_count += 1
                except Exception:
                    pass

            # Workout & Tonnage
            day_workouts = workouts_by_date.get(day_d, [])
            day_tonnage = 0.0
            workout_label = "Отдых"
            if day_workouts:
                workout_days_count += len(day_workouts)
                titles = []
                for dw in day_workouts:
                    an = self.analyzer.analyze_workout(dw)
                    t_kg = an.get("total_tonnage_kg", 0.0)
                    day_tonnage += t_kg
                    titles.append(dw.get("title", "Тренировка"))
                total_tonnage += day_tonnage
                t_str = f"{day_tonnage / 1000:.1f}т" if day_tonnage >= 1000 else f"{int(day_tonnage)}кг"
                w_title_short = titles[0][:9]
                workout_label = f"{w_title_short} ({t_str})"

            # Weight tracking for the week
            day_w = weight_history.get(day_str)
            if day_w:
                if first_weight is None:
                    first_weight = round(day_w, 1)
                    first_weight_date = day_d.strftime("%d.%m")
                last_weight = round(day_w, 1)
                last_weight_date = day_d.strftime("%d.%m")

            # Format row
            cal_str = str(cal) if has_nut else "—"
            macros_str = f"{int(prot)}/{int(fat)}/{int(carb)}" if has_nut else "—"

            daily_rows.append({
                "day_label": day_label,
                "cal_str": cal_str,
                "macros_str": macros_str,
                "workout_label": workout_label,
                "has_nut": has_nut,
                "has_workout": bool(day_workouts)
            })

        # Fallback for start/end weight if none recorded on Monday-Sunday directly
        if first_weight is None or last_weight is None:
            try:
                prof = self.yazio.get_user_profile() if self.yazio.is_configured() else {}
                cur_w = prof.get("current_weight_kg")
                if first_weight is None:
                    past_weights = {k: v for k, v in weight_history.items() if k <= monday.strftime("%Y-%m-%d")}
                    if past_weights:
                        closest_k = max(past_weights.keys())
                        first_weight = round(past_weights[closest_k], 1)
                        first_weight_date = datetime.strptime(closest_k, "%Y-%m-%d").strftime("%d.%m")
                    else:
                        first_weight = cur_w
                        first_weight_date = monday.strftime("%d.%m")
                if last_weight is None:
                    last_weight = cur_w
                    last_weight_date = ref_date.strftime("%d.%m")
            except Exception:
                pass

        # Build table
        table_lines = [
            " День | Ккал |   Б/Ж/У   | Тренировка (Тоннаж)",
            "──────┼──────┼───────────┼────────────────────"
        ]
        for r in daily_rows:
            d_col = r["day_label"].ljust(5)
            c_col = r["cal_str"].rjust(5)
            m_col = r["macros_str"].center(10)
            w_col = r["workout_label"]
            table_lines.append(f" {d_col}|{c_col} |{m_col} | {w_col}")

        table_block = "```\n" + "\n".join(table_lines) + "\n```"

        # Calculate averages
        avg_cal = round(total_calories / logged_days_count) if logged_days_count > 0 else 0
        avg_prot = round(total_protein / logged_days_count, 1) if logged_days_count > 0 else 0
        avg_fat = round(total_fat / logged_days_count, 1) if logged_days_count > 0 else 0
        avg_carb = round(total_carbs / logged_days_count, 1) if logged_days_count > 0 else 0

        # Weight delta
        w_delta_str = ""
        if first_weight is not None and last_weight is not None:
            delta = round(last_weight - first_weight, 2)
            if delta < 0:
                w_delta_str = f"*-{abs(delta):.1f} кг* 🔥 (отличный темп похудения!)"
            elif delta > 0:
                w_delta_str = f"*+{delta:.1f} кг* (возможна задержка воды или гликогена)"
            else:
                w_delta_str = "*0.0 кг* (стабильный вес)"

        w_summary = (
            f"⚖️ *Динамика веса за неделю:*\n"
            f"• В начале недели ({first_weight_date or 'Пн'}): *{first_weight or '—'} кг*\n"
            f"• В конце недели ({last_weight_date or 'Вс'}): *{last_weight or '—'} кг*\n"
            f"• Изменение за неделю: {w_delta_str}"
        )

        nut_summary = (
            f"🥗 *Питание за неделю (в среднем за {logged_days_count} дн.):*\n"
            f"• Калораж: *{avg_cal:,} ккал/день*\n"
            f"• Белки: *{avg_prot} г/день* (целевая норма: 158–198 г)\n"
            f"• Жиры: *{avg_fat} г/день*  |  Углеводы: *{avg_carb} г/день*"
        )

        workout_summary = (
            f"🏋️ *Тренировочный объем в Hevy:*\n"
            f"• Проведено силовых сессий: *{workout_days_count}*\n"
            f"• Суммарный тоннаж за неделю: *{total_tonnage:,.0f} кг* (~{total_tonnage/1000:.1f} тонн поднятого веса! 💪)"
        )

        # Coaching conclusion
        coach_advice = []
        if avg_prot >= 155:
            coach_advice.append("✅ *Белок в идеале*: мышцы надёжно защищены от катаболизма во время дефицита.")
        elif avg_prot > 0:
            coach_advice.append("⚠️ *Белок чуть ниже нормы*: постарайся добавить 1–2 порции нежирного творога, филе или протеина.")

        if 1700 <= avg_cal <= 2100:
            coach_advice.append("🎯 *Калории*: дефицит выдержан оптимально, процесс жиросжигания идёт стабильно без стресса для ЦНС.")
        elif avg_cal > 2100:
            coach_advice.append("ℹ️ *Калории*: калораж близок к уровню поддержки, держи фокус на дефиците.")

        if workout_days_count >= 3:
            coach_advice.append(f"🔥 *Объем нагрузок*: суммарно поднято {total_tonnage:,.0f} кг — отличная дисциплина и прогресс!")

        advice_block = "\n".join([f"• {a}" for a in coach_advice]) if coach_advice else "• Продолжай в том же духе, держим курс на 80 кг!"

        report = (
            f"📊 *ИТОГИ НЕДЕЛИ ({monday.strftime('%d.%m')} — {sunday.strftime('%d.%m.%Y')})*\n\n"
            f"{table_block}\n\n"
            f"{w_summary}\n\n"
            f"{nut_summary}\n\n"
            f"{workout_summary}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Резюме и рекомендации тренера:*\n"
            f"{advice_block}"
        )
        return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hevy & Yazio AI Coach CLI")
    parser.add_argument("command", choices=["last", "next", "weekly", "sync", "prog", "nutrition", "weekly_nutrition", "products", "profile"], nargs="?", default="last",
                        help="Command to run: last, next, weekly, sync, prog, nutrition, weekly_nutrition, products, profile")
    parser.add_argument("--exercise", "-e", type=str, help="Exercise name for 'prog' command", default="")
    parser.add_argument("--date", "-d", type=str, help="Date for 'nutrition' / 'products' command (YYYY-MM-DD)", default="")

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
    elif args.command == "weekly_nutrition":
        print(coach.get_weekly_nutrition_report())
    elif args.command == "products":
        print(coach.get_consumed_products_report(args.date if args.date else None))
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
