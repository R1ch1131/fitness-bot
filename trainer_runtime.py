"""AI and workout context for the web app; no messaging-platform clients."""
import os, sys, json, time, threading, collections
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone, timedelta
from config import DATA_DIR
from coach import AIHevyCoach
RECENT_LOGS = collections.deque(maxlen=150)
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
coach = AIHevyCoach(auto_sync=False)
_context_cache = {'timestamp': 0, 'instruction': ''}


class LogInterceptor:
    def __init__(self, original):
        self.original = original
    def write(self, s):
        if s.strip():
            timestamp = datetime.now(timezone(timedelta(hours=6))).strftime("%H:%M:%S")
            RECENT_LOGS.append(f"[{timestamp}] {s.strip()}")
        try:
            self.original.write(s)
        except Exception:
            pass
    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass
    def isatty(self):
        return getattr(self.original, "isatty", lambda: False)()
    def __getattr__(self, name):
        return getattr(self.original, name)

MODELS_CASCADE = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview"
]

def get_system_instruction() -> str:
    """Builds and caches detailed coaching context for Gemini for 10 minutes."""
    now = time.time()
    if _context_cache["instruction"] and (now - _context_cache["timestamp"] < 60):
        return _context_cache["instruction"]

    try:
        if not coach.workouts or not coach.routines:
            coach.reload(auto_sync=True)

        prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
        w_cur = prof.get("current_weight_kg", 98.8)
        h_cur = prof.get("height_cm", 182)
        age = prof.get("age", 22)
        start_w = prof.get("start_weight_kg", 103.0)

        routines_context = ""
        for r in coach.routines:
            ex_names = ", ".join([coach.translate_exercise_title(e.get("title", ""), e.get("exercise_template_id")) for e in r.get("exercises", [])])
            routines_context += f"- {r.get('title')}: {ex_names}\n"

        last_w = coach.analyzer.get_latest_workout()
        last_w_str = f"{last_w.get('title')} ({last_w.get('start_time')})" if last_w else "нет записей"

        weekly_nut_text = "Данные о недельном питании пока не загружены."
        try:
            if coach.yazio.is_configured():
                wn = coach.yazio.get_weekly_nutrition(days_count=7)
                if wn and wn.get("days"):
                    days_str = "; ".join([f"{d['date']} ({d['weekday']}): {d['calories']} ккал (Б:{d['protein']}г, Ж:{d['fat']}г, У:{d['carbs']}г)" for d in wn["days"] if d.get("is_logged")])
                    weekly_nut_text = (
                        f"За последние 7 дней (с {wn.get('start_date')} по {wn.get('end_date')}):\n"
                        f"- Средний калораж: {wn.get('avg_calories')} ккал/день\n"
                        f"- Средний белок: {wn.get('avg_protein')} г/день (целевая норма: 158-198 г)\n"
                        f"- Средние жиры: {wn.get('avg_fat')} г/день\n"
                        f"- Средние углеводы: {wn.get('avg_carbs')} г/день\n"
                        f"- По дням недели: {days_str}"
                    )
        except Exception as e:
            print(f"Weekly nut context note: {e}")

        products_text = "Продукты за сегодня еще не записаны."
        try:
            if coach.yazio.is_configured():
                cp = coach.yazio.get_consumed_products()
                if cp and cp.get("meals"):
                    meals_str = []
                    for m_name, items in cp["meals"].items():
                        item_strs = [f"{it['name']}{' (' + it['producer'] + ')' if it.get('producer') else ''} {it.get('amount_g')}г" for it in items]
                        meals_str.append(f"{m_name}: {', '.join(item_strs)}")
                    products_text = "\n".join(meals_str)
        except Exception as e:
            print(f"Products context note: {e}")

        recent_feedback_context = ""
        try:
            pending = load_pending_checkin()
            if pending and pending.get("last_user_feedback"):
                last_fb_age = time.time() - pending.get("last_feedback_time", 0)
                if last_fb_age < 12 * 3600:
                    recent_feedback_context = f"- Недавние ощущения и вопросы атлета после тренировки: «{pending['last_user_feedback']}»\n"
        except Exception:
            pass

        now_gmt6 = datetime.now(timezone(timedelta(hours=6)))
        today_date_str = now_gmt6.strftime("%Y-%m-%d")
        weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        today_weekday = weekdays_ru[now_gmt6.weekday()]
        current_time_str = now_gmt6.strftime("%H:%M")
        habits_summary = ""
        habits_summary = ""
        try:
            from habits_manager import HabitsManager
            hm = HabitsManager()
            hm.sync_with_hevy_and_yazio(coach)
            habits_summary = hm.get_habits_ai_summary()
        except Exception as he:
            habits_summary = f"Данные привычек временно недоступны: {he}"

        library_summary = ""
        try:
            from books_manager import BooksManager
            library_summary = BooksManager().get_library_ai_summary()
        except Exception as be:
            library_summary = f"Библиотека временно недоступна: {be}"

        instruction = f"""
Ты — универсальный персональный AI-наставник, элитный спортивный тренер, нутрициолог, кулинарный шеф и ментор по саморазвитию и программированию для атлета.
Текущая дата и время: {today_date_str} ({today_weekday}), {current_time_str} GMT+6.
- Атлет: Мужчина, Возраст: {age} года (30.06.2004), Рост: {h_cur} см.
- Вес: {w_cur} кг (начальный вес: {start_w} кг, сброшено: {abs(w_cur - start_w):.1f} кг, цель: 80 кг). Текущий режим: качественная сушка/похудение с сохранением сухой мышечной массы, дефицит калорий (~1900-2000 ккал/день), белок 160-200 г/день.
- Тренировочные программы в Hevy (5-дневный сплит):
{routines_context}
- Последняя проведенная тренировка: {last_w_str}.
{recent_feedback_context}- Кардио: бег 3-4 км в темпе ~10 км/ч (в день ног — ходьба в гору для защиты коленей).
- Питание атлета (YAZIO):
  * Недельный рацион и средние значения:
{weekly_nut_text}
  * Продукты, съеденные сегодня:
{products_text}
- Трекер привычек и целей атлета:
{habits_summary}
- Библиотека и прочитанные книги атлета:
{library_summary}

ТВОИ КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ И ПРАВИЛА ОБЩЕНИЯ:
1. СПОРТ И ТРЕНИРОВКИ: техника упражнений, прогрессивная перегрузка, периодизация, разминка/заминка, биомеханика, выбор рабочих весов, профилактика травм.
2. ПИТАНИЕ, РЕЦЕПТЫ И ДОБАВКИ:
   - Если атлет спрашивает: "Что съесть?", "Рецепт", "Варианты ужина/обеда на X ккал" — ВСЕГДА предлагай конкретные, аппетитные, легкодоступные блюда с точным расчетом граммовок, калорий и БЖУ (например: 180г запеченной куриной грудки, 200г брокколи на пару с 5г оливкового масла, 100г нежирного творога 5% с щепоткой корицы = 390 ккал, 48г белка).
   - Если спрашивает про БАДы (креатин, сывороточный протеин, омега-3, витамин D3, цинк, магний и др.) — давай научно обоснованные советы по таймингу приема и дозировкам.
3. ПРОГРАММИРОВАНИЕ И IT (одна из ключевых привычек атлета — кодинг от 30 мин/день):
   - Если атлет спрашивает про программирование (Python, бэкенд, алгоритмы, базы данных, веб-разработку, чистый код или планирование учебной сессии) — отвечай на уровне опытного Senior разработчика: давай лаконичные, работающие примеры кода, архитектурные советы и понятные аналогии.
4. КНИГИ И САМОРАЗВИТИЕ (привычка — чтение от 10 страниц/день):
   - Советуй сильные книги по продуктивности, дисциплине, психологии, биохакингу, бизнесу и IT.
   - Никаких спойлеров для читаемых и запланированных книг: ни событий, ни концовок, ни судеб персонажей, ни намёков на будущее.
   - Номер страницы не определяет пройденный сюжет: издания отличаются. Не заявляй, что знаешь, какие события уже прочитаны.
   - Комментируй прогресс и добавляй живые отсылки к уже знакомым пользователю деталям по правилам ответа ниже. Не раскрывай неизвестные ему события.
5. ТРЕКЕР ПРИВЫЧЕК И ДИСЦИПЛИНА:
   - Поддерживай стрики атлета, подбадривай, хвали за регулярность.
   - Если атлет пишет во второй половине дня, а важные привычки (зал, чтение, кодинг, питание) еще не отмечены — дружески и ненавязчиво напомни закрыть их.
6. ИНТЕЛЛЕКТ И ТОН ДИАЛОГА:
   - Общайся как умный, надежный старший товарищ и персональный коуч: с уважением, драйвом, легким юмором, без душности и без сухих роботизированных шаблонов.
   - Отвечай прямо на поставленный вопрос, избегай шаблонных отписок о текущем дефиците, если вопрос был про рецепт, код или книгу.
   - Язык: русский.
"""
        _context_cache["instruction"] = instruction
        _context_cache["timestamp"] = now
        return instruction
    except Exception as e:
        print(f"Error building system instruction: {e}")
        return _context_cache["instruction"] or "Ты — персональный спортивный тренер атлета."

def ask_gemini_ai(user_question: str, force_llm: bool = False, history: Optional[List[Dict[str, str]]] = None, extra_context: str = "", context_only: bool = False) -> str:
    """Uses Gemini API with cascaded model fallbacks, multi-turn history context, and robust error handling."""
    q_lower = user_question.lower().strip()

    # If force_llm is True or if the user asks a real question/conversational prompt, skip fast-path shortcuts!
    is_conversational = (
        force_llm or
        "?" in user_question or
        any(q_lower.startswith(p) for p in [
            "что ", "как ", "почему ", "сколько ", "посоветуй", "подскажи", "какой ", "какая ", "какие ",
            "рецепт", "приготов", "вариант", "идеи", "можно ли", "стоит ли", "код", "прог", "книг", "напиши"
        ]) or
        any(w in q_lower for w in ["рецепт", "приготовить", "что съесть", "посоветуй", "python", "питон", "программир", "книг", "прочита"])
    )

    if not is_conversational:
        # Fast-path direct handlers ONLY for exact button clicks or exact command phrases
        if q_lower in ["🍽 что я ел (продукты)", "что я ел", "мои продукты", "продукты", "/products"]:
            return coach.get_consumed_products_report()
        if q_lower in ["📊 питание за неделю", "питание за неделю", "/week_nutrition"]:
            return coach.get_weekly_nutrition_report()
        if q_lower in ["📋 план на тренировку", "план на тренировку", "/next"]:
            return coach.preview_next_workout()
        if q_lower in ["🏋️ последняя тренировка", "последняя тренировка", "/last"]:
            return coach.review_last_workout()
        if q_lower in ["⏳ прогноз к 80 кг", "прогноз к 80 кг", "/eta"]:
            return coach.get_goal_eta_report()
        if q_lower in ["🌙 вечерний чек-ин", "вечерний чек-ин", "/evening"]:
            return coach.get_evening_nutrition_checkin()
        if q_lower in ["🥗 питание (сегодня)", "питание сегодня", "питание (yazio)", "/today", "/nutrition"]:
            return coach.get_nutrition_report()
        if q_lower in ["👤 мой профиль и вес", "мой профиль", "мой вес", "профиль", "/profile", "вес"]:
            return coach.get_profile_report()
        if q_lower in ["📈 недельный отчет", "недельный отчет", "/weekly"]:
            return coach.get_sunday_weekly_table_report()

    # Query Gemini models with full fallback cascade
    if GEMINI_KEY:
        try:
            from google import genai
            client = genai.Client(
                api_key=GEMINI_KEY,
                http_options={"timeout": 18_000}
            )
            system_instruction = (
                "Ты — персональный спортивный наставник. Отвечай на русском. Используй только переданные факты выбранного периода. "
                "Не считай отсутствие записей нулевым сном и не ставь диагноз по часам."
                if context_only else get_system_instruction()
            )
            from coach_memory import ai_context as memory_context
            memory = memory_context()
            if memory:
                system_instruction += "\n\n" + memory
            if extra_context:
                system_instruction += "\n\nДополнительные данные для этого запроса:\n" + extra_context

            from response_style import RESPONSE_STYLE
            system_instruction += "\n\n" + RESPONSE_STYLE

            contents_text = f"Вопрос атлета: {user_question}"
            if history and isinstance(history, list):
                valid_turns = []
                for t in history[-6:]:
                    role = "Атлет" if t.get("role") in ["user", "athlete"] or t.get("sender") == "user" else "Тренер"
                    text_val = (t.get("text") or "").strip()
                    if text_val:
                        valid_turns.append(f"{role}: {text_val}")
                if valid_turns:
                    history_context = "\n".join(valid_turns)
                    contents_text = f"Контекст последних сообщений диалога:\n{history_context}\n\nНовый вопрос атлета: {user_question}"

            for model_name in MODELS_CASCADE:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents_text,
                        config={"system_instruction": system_instruction}
                    )
                    if response and response.text:
                        return response.text
                except Exception as model_err:
                    print(f"Model {model_name} failed ({type(model_err).__name__}: {model_err}), trying fallback...")
                    continue
        except Exception as e:
            print(f"Gemini client setup error: {e}")

    return "⚠️ Сервер ИИ временно перегружен или недоступен. Пожалуйста, повтори свой вопрос через пару секунд."

def analyze_post_workout_feedback(user_feedback: str, workout_id: Optional[str] = None, daily_context: Optional[str] = None, reading_progress: str = "", extra_context: str = "") -> str:
    """Correlates athlete's subjective feedback with actual Hevy workout metrics using Gemini AI."""
    workout = None
    if workout_id:
        for w in coach.workouts:
            if w.get("id") == workout_id:
                workout = w
                break
    if not workout:
        workout = coach.analyzer.get_latest_workout()

    if not workout:
        return "⚠️ Не удалось найти данные о тренировке для сопоставления. Нажми '🔄 Синхронизация'."

    try:
        an = coach.analyzer.analyze_workout(workout)
        w_title = an.get("title", "Тренировка")
        duration = an.get("duration_minutes", 0)
        tonnage = an.get("total_tonnage_kg", 0)
        sets_count = an.get("total_working_sets", 0)
        w_date = an.get("date", "")

        ex_lines = []
        for ex in an.get("exercises", []):
            sets_s = " | ".join(ex.get("sets_formatted", []))
            ex_lines.append(f"• {ex['title']} ({ex['muscle']}): {sets_s} [Макс: {ex['max_weight_kg']} кг, Тоннаж: {ex['tonnage_kg']:,.0f} кг]")
        exercises_text = "\n".join(ex_lines) if ex_lines else "Данные по упражнениям отсутствуют"

        cardio_text = "Без кардио"
        if an.get("cardio"):
            c_items = [f"{c['title']} ({c.get('distance_km', 0)} км за {c.get('duration_minutes', 0)} мин, темп {c.get('pace_min_km', '')})" for c in an["cardio"]]
            cardio_text = "; ".join(c_items)

        from response_style import post_workout_prompt
        workout_context = (
            f"Программа: {w_title} ({w_date}).\n"
            f"Длительность: {duration} мин. Тоннаж: {tonnage:,.0f} кг. Рабочих подходов: {sets_count}.\n"
            f"Упражнения и подходы:\n{exercises_text}\nКардио: {cardio_text}"
        )
        if daily_context is None:
            from daily_review import collect_daily_review
            daily_context, reading_progress = collect_daily_review(coach)
        if extra_context:
            daily_context += "\n" + extra_context
        from coach_memory import ai_context as memory_context
        memory = memory_context()
        if memory:
            daily_context += "\n" + memory
        prompt = post_workout_prompt(workout_context, user_feedback, daily_context)

        # Try Gemini models cascade
        if GEMINI_KEY:
            try:
                from google import genai
                client = genai.Client(
                    api_key=GEMINI_KEY,
                    http_options={"timeout": 12_000}  # 12 sec timeout
                )
                print(f"[FEEDBACK] Prompt length: {len(prompt)} chars")
                for model_name in MODELS_CASCADE:
                    try:
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        if resp and resp.text:
                            print(f"[FEEDBACK] Model {model_name} responded OK, length: {len(resp.text)}")
                            return f"📋 *Тренировка и итоги дня:*\n\n{resp.text}"
                    except Exception as model_err:
                        print(f"Model {model_name} failed for feedback analysis: {model_err}")
                        continue
            except Exception as e:
                print(f"Gemini client feedback analysis error: {e}")

        # Deterministic fallback if Gemini is unreachable
        return (
            f"📋 *Анализ тренировки: {w_title}*\n\n"
            f"⏱ Длительность: *{duration} мин* | Тоннаж: *{tonnage:,.0f} кг* ({sets_count} раб. подходов)\n\n"
            f"💬 *Твой отзыв:* «_{user_feedback}_»\n\n"
            "ИИ сейчас недоступен — разбор не сформирован. Попробуй ещё раз позже."
        ) + (f"\n\n{reading_progress}" if reading_progress else "")
    except Exception as err:
        print(f"Error in analyze_post_workout_feedback: {err}")
        return "⚠️ Не удалось сформировать отчет по самочувствию. Попробуй позже."

def check_for_new_workouts_and_sync(bot=None):
    """Checks Hevy API for new workouts, performs auto-sync, and schedules 20-min checkin."""
    try:
        client = getattr(coach, "hevy", None) or getattr(coach.storage, "client", None)
        if not client or not getattr(client, "api_key", None):
            return

        current_count = client.get_workouts_count()
        tracker = load_workout_tracker()
        last_count = tracker.get("last_known_count", 0)
        last_id = tracker.get("last_known_id")

        # Fetch latest workout from Hevy API
        latest_api_resp = client.get_workouts(page=1, page_size=1)
        api_workouts = latest_api_resp.get("workouts", [])
        if not api_workouts:
            return

        latest_api_w = api_workouts[0]
        latest_api_id = latest_api_w.get("id")

        # Check if new workout detected
        is_new = False
        if current_count > last_count:
            is_new = True
        elif last_id and latest_api_id != last_id:
            is_new = True
        elif not last_id or len(coach.workouts) < current_count:
            is_new = True

        if is_new:
            print(f"🎉 Обнаружена новая тренировка в Hevy: {latest_api_w.get('title')} (ID: {latest_api_id})! Выполняю автосинхронизацию...")
            coach.storage.sync_all(verbose=False)
            coach.reload(auto_sync=False)
            _context_cache["timestamp"] = 0

            tracker["last_known_count"] = current_count
            tracker["last_known_id"] = latest_api_id
            save_workout_tracker(tracker)

        # Check if latest workout needs post-workout checkin
        latest_workout = coach.analyzer.get_latest_workout()
        if not latest_workout:
            return

        w_id = latest_workout.get("id")
        w_title = latest_workout.get("title", "Тренировка")
        end_iso = latest_workout.get("end_time")

        from analyzer import parse_iso
        end_dt = parse_iso(end_iso) if end_iso else None
        now_ts = time.time()

        # Check if workout ended recently (within last 24 hours)
        is_recent = False
        if end_dt:
            hours_ago = (now_ts - end_dt.timestamp()) / 3600
            if 0 <= hours_ago <= 24:
                is_recent = True

        pending = load_pending_checkin()
        already_prompted = (
            (tracker.get("last_prompted_id") == w_id) or
            (pending.get("workout_id") == w_id and pending.get("prompt_sent"))
        )

        if is_recent and not already_prompted:
            if end_dt:
                target_due = end_dt.timestamp() + (20 * 60)
            else:
                target_due = now_ts + (20 * 60)

            # If ended >20 min ago, schedule prompt in 5 seconds
            if target_due < now_ts:
                target_due = now_ts + 5

            new_pending = {
                "workout_id": w_id,
                "workout_title": w_title,
                "end_time": end_iso,
                "due_time": target_due,
                "prompt_sent": False,
                "prompt_sent_time": 0.0,
                "responded": False
            }
            save_pending_checkin(new_pending)
            tracker["last_prompted_id"] = w_id
            save_workout_tracker(tracker)
            print(f"⏰ Запланирован опрос о тренировке «{w_title}» (целевое время: {target_due})")

    except Exception as e:
        print(f"Error in check_for_new_workouts_and_sync: {e}")


def load_workout_tracker():
    from notification_settings import _read
    return _read('workout_tracker', {})


def save_workout_tracker(data):
    from notification_settings import _write
    _write('workout_tracker', data)


def load_pending_checkin():
    from notification_settings import _read
    return _read('pending_checkin', {})


def save_pending_checkin(data):
    from notification_settings import _write
    _write('pending_checkin', data)


def dispatch_checkin_if_due(bot=None, target_chat_id=None):
    from notification_settings import dispatch_workout_push
    pending = load_pending_checkin()
    if pending and dispatch_workout_push(pending, time.time()):
        pending['push_sent'] = True
        save_pending_checkin(pending)
