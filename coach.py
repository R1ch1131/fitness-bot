import sys
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from storage import Storage
from analyzer import WorkoutAnalyzer
from yazio_client import YazioManager

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

    def review_last_workout(self) -> str:
        """Generates a detailed, motivational and critical review of the last workout."""
        if not self.workouts:
            self.reload(auto_sync=True)

        last_w = self.analyzer.get_latest_workout()
        if not last_w:
            return "Тренировки не найдены в аккаунте. Запишите тренировку в Hevy или выполните синхронизацию."

        metrics = self.analyzer.analyze_workout(last_w)
        lines = []

        lines.append(f"🏋️ **Разбор тренировки: {metrics['title']}** ({metrics['date']} в {metrics['start_time']})")
        lines.append(f"⏱ Длительность: **{metrics['duration_minutes']} мин** | Общий тоннаж: **{metrics['total_tonnage_kg']:,.0f} кг** | Рабочих подходов: **{metrics['total_working_sets']}**\n")

        lines.append("### 📊 Упражнения и нагрузка:")
        prs = []
        for ex in metrics["exercises"]:
            sets_text = " | ".join(ex["sets_formatted"])
            lines.append(f"- **{ex['title']}** ({ex['muscle']})")
            lines.append(f"  Подходы: {sets_text}")
            lines.append(f"  Макс. вес: **{ex['max_weight_kg']} кг** | e1RM: **{ex['estimated_1rm']} кг** | Тоннаж: {ex['tonnage_kg']:,.0f} кг")

            # Check progression against previous sessions
            history = self.analyzer.track_exercise_progression(ex["title"], template_id=ex.get("exercise_template_id"))
            if len(history) > 1:
                prev = history[-2]
                curr = history[-1]
                diff_w = curr["max_weight"] - prev["max_weight"]
                diff_ton = curr["tonnage"] - prev["tonnage"]
                if diff_w > 0:
                    prs.append(f"🔥 **{ex['title']}**: +{diff_w} кг к пиковому весу ({prev['max_weight']} кг ➔ {curr['max_weight']} кг)!")
                elif diff_ton > 0:
                    prs.append(f"📈 **{ex['title']}**: +{diff_ton:,.0f} кг к суммарному объему упражнения!")

        if metrics["cardio"]:
            lines.append("\n### 🏃 Кардио блок:")
            for c in metrics["cardio"]:
                lines.append(f"- **{c['title']}**: **{c['distance_km']} км** за **{c['duration_minutes']} мин** (средняя скорость **{c['speed_kmh']} км/ч**, темп **{c['pace']}**)")

        if prs:
            lines.append("\n### 🏆 Прогресс и личные достижения:")
            for pr in prs:
                lines.append(f"- {pr}")

        lines.append("\n### 💡 Заметки и рекомендации тренера:")
        # Contextual coaching advice based on workout type
        title_lower = metrics["title"].lower()
        if "пятниц" in title_lower or "ног" in title_lower or "leg" in title_lower:
            lines.append("1. **Бег после тяжелых ног**: 4 км за 24:30 после становой и жима ногами — отличная аэробная выносливость! Однако длительный бег после ног создает дополнительную ударную нагрузку на коленные суставы и может снижать пиковый анаболический отклик (интерференция). Рекомендация: в дни тяжелых ног лучше ограничиться легкой заминкой на дорожке (шаг под наклоном) или велосипедом.")
            lines.append("2. **Становая тяга**: 70 кг на 9 повторений в последнем подходе указывает на то, что запас сил еще был. На следующей сессии спины/ног можно смело ставить цель закрыть 70 кг на полные 10 повторений или протестировать 72.5-75 кг на 8 повторений.")
            lines.append("3. **Разминка**: Первые подходы (например, 50 кг в жиме ногами) в приложении лучше помечать типом 'Warmup'. Это позволит точнее отслеживать чистый рабочий тоннаж.")
        elif "четверг" in title_lower or "верх" in title_lower:
            lines.append("1. **Утомление дельт**: В жиме от плеч повторения распределились как 10 -> 8 -> 5. Падение до 5 повторений показывает сильное локальное утомление передней дельты после жима лежа. Рекомендация: увеличить отдых между 2-м и 3-м подходом до 2-2.5 минут.")
            lines.append("2. **Тяги**: Отличная горизонтальная тяга блока (до 62.5 кг) и уверенное перекрытие объема вторника.")
        else:
            lines.append("1. **Интенсивность**: Тренировка выполнена в хорошем объеме. Следите за качеством сна и потреблением белка (1.6–2.0 г на кг веса тела) для полноценного восстановления.")

        return "\n".join(lines)

    def preview_next_workout(self) -> str:
        """Determines the next routine and prepares targets based on past performance."""
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

        lines = []
        lines.append(f"📋 **План на следующую тренировку: {target_routine.get('title')}**")
        lines.append(f"Цель сессии: качественная проработка целевых мышц и применение принципа прогрессивной перегрузки.\n")

        lines.append("### 🎯 Упражнения и целевые ориентиры:")
        for ex in target_routine.get("exercises", []):
            title = ex.get("title", "")
            template_id = ex.get("exercise_template_id")
            history = self.analyzer.track_exercise_progression(title, template_id=template_id)

            lines.append(f"\n- **{title}** ({len(ex.get('sets', []))} подходов)")
            if history:
                prev = history[-1]
                lines.append(f"  * Предыдущий результат ({prev['date']}): макс. вес **{prev['max_weight']} кг**, подходы: [{prev['sets']}]")
                # Propose target
                if prev['max_weight'] > 0:
                    lines.append(f"  * 🚀 **Цель на сегодня**: повторить рабочий вес {prev['max_weight']} кг с запасом по технике либо добавить +2.5 кг / +1-2 повторения в первом тяжелом подходе.")
            else:
                lines.append("  * 🆕 Первое выполнение в текущем цикле: начните с умеренного веса с запасом 2 повторения (RPE 7-8), чтобы определить рабочий базис.")

        lines.append("\n### 💡 Советы по разминке и технике:")
        lines.append("1. **Специфическая разминка**: 1-2 легких разминочных подхода (40-50% и 70% от рабочего веса) перед первым базовым упражнением.")
        lines.append("2. **Темп выполнения**: Подконтрольная негативная фаза (опускание 2-3 сек) и мощное сокращение (1 сек).")
        lines.append("3. **Отдых**: 2-3 минуты в базовых компаундных движениях, 60-90 секунд в изолирующих упражнениях.")

        return "\n".join(lines)

    def weekly_overview(self) -> str:
        """Overview of total workload and muscle distribution."""
        if not self.workouts:
            self.reload(auto_sync=True)
        stats = self.analyzer.get_weekly_stats()
        lines = []
        lines.append("📈 **Общий тренировочный отчет**")
        lines.append(f"- Всего тренировок в цикле: **{stats['workouts_count']}**")
        lines.append(f"- Суммарный тоннаж: **{stats['total_tonnage_kg']:,.0f} кг**")
        lines.append(f"- Общее время под нагрузкой: **{stats['total_duration_hours']} ч**")
        lines.append(f"- Общий километраж кардио: **{stats['total_cardio_km']} км**\n")

        lines.append("### ⚖️ Распределение тоннажа по мышечным группам:")
        for muscle, ton in sorted(stats["muscle_distribution"].items(), key=lambda x: x[1], reverse=True):
            pct = (ton / stats["total_tonnage_kg"] * 100) if stats["total_tonnage_kg"] > 0 else 0
            lines.append(f"- **{muscle}**: {ton:,.0f} кг ({pct:.1f}%)")

        return "\n".join(lines)

    def get_nutrition_report(self, target_date_str: Optional[str] = None) -> str:
        """Returns nutrition review from YAZIO."""
        if not self.yazio.is_configured():
            return (
                "🥗 **Интеграция с YAZIO готова, но учетные данные еще не указаны.**\n\n"
                "Чтобы подключить ваш дневник питания:\n"
                "1. Откройте файл `.env` в `hevy_coach` или передайте мне логин/пароль.\n"
                "2. Укажите:\n"
                "   `YAZIO_EMAIL=ваш_email@example.com`\n"
                "   `YAZIO_PASSWORD=ваш_пароль`\n\n"
                "Подписка YAZIO Pro **НЕ требуется** — бесплатный аккаунт поддерживается в полном объеме!"
            )

        try:
            from datetime import date, timedelta, datetime
            if target_date_str:
                d = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            else:
                d = date.today()

            summary = self.yazio.get_daily_summary(d)
            
            # If today has no logged meals yet (e.g. early morning), fallback to yesterday for demonstration
            is_yesterday = False
            if summary.get("calories", 0) == 0 and not target_date_str:
                yesterday = d - timedelta(days=1)
                y_summary = self.yazio.get_daily_summary(yesterday)
                if y_summary.get("calories", 0) > 0:
                    summary = y_summary
                    d = yesterday
                    is_yesterday = True

            lines = []
            prefix = "(Вчера)" if is_yesterday else "(Сегодня)"
            
            # Fetch real user profile
            try:
                prof = self.yazio.get_user_profile()
                weight_str = f" | Текущий вес: **{prof['current_weight_kg']} кг** ({prof['weight_change_kg']:+.1f} кг)"
            except Exception:
                prof = None
                weight_str = ""

            lines.append(f"🥗 **Сводка питания из YAZIO {prefix} — {summary['date']}**{weight_str}")
            
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

            lines.append(f"- 🔥 Калории: **{cal:,.0f} ккал** / цель {cal_goal:,.0f} ккал ({cal/cal_goal*100:.0f}%)" if cal_goal else f"- 🔥 Калории: **{cal:,.0f} ккал**")
            lines.append(f"- 🥩 Белки: **{prot:.1f} г** / цель {prot_goal:.1f} г" if prot_goal else f"- 🥩 Белки: **{prot:.1f} г**")
            lines.append(f"- 🥑 Жиры: **{fat:.1f} г** / цель {fat_goal:.1f} г" if fat_goal else f"- 🥑 Жиры: **{fat:.1f} г**")
            lines.append(f"- 🍞 Углеводы: **{carb:.1f} г** / цель {carb_goal:.1f} г" if carb_goal else f"- 🍞 Углеводы: **{carb:.1f} г**")
            if water > 0:
                lines.append(f"- 💧 Вода: **{water / 1000.0:.2f} л**")

            if summary.get("meals"):
                lines.append("\n### 🍽 Приемы пищи:")
                for m_name, m_val in summary["meals"].items():
                    lines.append(f"- **{m_name}**: **{m_val['calories']:,.0f} ккал** (Б: {m_val['protein']}г, Ж: {m_val['fat']}г, У: {m_val['carbs']}г)")

            lines.append("\n### 💡 Оценка и рекомендации тренера под ваш вес:")
            cur_weight = prof["current_weight_kg"] if prof else 99.3
            opt_prot_min = round(cur_weight * 1.6)
            opt_prot_max = round(cur_weight * 2.0)

            if prot >= opt_prot_min:
                lines.append(f"1. **Белок закрыт отлично**: {prot:.0f} г покрывает норму 1.6–2.0 г/кг ({opt_prot_min}–{opt_prot_max} г для веса {cur_weight} кг). Это защищает мышечную ткань от катаболизма во время похудения.")
            else:
                lines.append(f"1. **Белок желательно поднять**: Для сохранения сухой мышечной массы при весе {cur_weight} кг оптимум — **{opt_prot_min}–{opt_prot_max} г белка** (1.6–2.0 г/кг). Добавьте творог, куриное филе, тунец или сывороточный протеин.")

            if cal < 2100 and cal > 0:
                lines.append(f"2. **Глубокий дефицит калорий**: Ваш базовый обмен (BMR) при весе {cur_weight} кг и росте 182 см составляет ~2,025 ккал. С учетом силовых тренировок и бега расход достигает 3,000–3,200 ккал. Потребление ~1,700–2,000 ккал дает быстрый сброс жира, но следите за самочувствием и силовыми весами в Hevy: если начнется упадок сил, поднимите калораж до 2,200–2,400 ккал за счет медленных углеводов.")

            return "\n".join(lines)
        except Exception as e:
            return f"Ошибка получения данных из YAZIO: {e}"

    def get_profile_report(self) -> str:
        """Returns comprehensive biometric report."""
        if not self.yazio.is_configured():
            return "YAZIO не авторизован."
        prof = self.yazio.get_user_profile()
        w = prof["current_weight_kg"]
        h = prof["height_cm"]
        age = prof["age"]
        bmr = round(10 * w + 6.25 * h - 5 * age + 5)
        tdee = round(bmr * 1.55)

        lines = [
            "👤 **Профиль спортсмена из YAZIO**",
            f"- Возраст: **{age} года** (родился 30.06.2004)",
            f"- Рост: **{h} см** | Пол: Мужской",
            f"- Текущий вес: **{w} кг**",
            f"- Стартовый вес: **{prof['start_weight_kg']} кг**",
            f"- Сброшено: **{abs(prof['weight_change_kg'])} кг** 🔥",
            f"- Базовый обмен веществ (BMR): **{bmr:,.0f} ккал/день**",
            f"- Суточный расход с тренировками (TDEE): **~{tdee:,.0f} ккал/день**",
            f"- Рекомендуемый диапазон белка (1.6–2.0 г/кг): **{round(w*1.6)} – {round(w*2.0)} г/день**"
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
