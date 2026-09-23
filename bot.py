import os
import sys
import json
import time
import threading
from contextlib import contextmanager
from datetime import datetime, date, timezone, timedelta
import telebot
from telebot import types

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import API_KEY as HEVY_KEY, DATA_DIR
from coach import AIHevyCoach

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

coach = AIHevyCoach(auto_sync=False)

SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
WORKOUT_TRACKER_FILE = DATA_DIR / "workout_tracker.json"
PENDING_CHECKIN_FILE = DATA_DIR / "pending_checkin.json"

# Cache for Gemini system instruction to avoid repetitive heavy YAZIO queries on every message
_context_cache = {
    "timestamp": 0,
    "instruction": ""
}

# Reliable active Gemini models in priority order
MODELS_CASCADE = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest"
]

def split_message(text: str, max_len: int = 3900) -> list:
    """Splits message into chunks under 4000 chars, preserving markdown/newlines."""
    if not text:
        return [""]
    if len(text) <= max_len:
        return [text]
    chunks = []
    current_text = text
    while current_text:
        if len(current_text) <= max_len:
            chunks.append(current_text)
            break
        idx = current_text.rfind("\n\n", 0, max_len)
        if idx == -1:
            idx = current_text.rfind("\n", 0, max_len)
        if idx == -1:
            idx = max_len
        chunk = current_text[:idx].strip()
        if chunk:
            chunks.append(chunk)
        current_text = current_text[idx:].strip()
    return chunks or [text[:max_len]]

def register_subscriber(chat_id: int):
    """Saves user chat_id for scheduled gym reminders and check-ins."""
    try:
        subscribers = []
        if SUBSCRIBERS_FILE.exists():
            try:
                with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                    subscribers = json.load(f)
            except Exception:
                subscribers = []
        if chat_id not in subscribers:
            subscribers.append(chat_id)
            with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                json.dump(subscribers, f, ensure_ascii=False, indent=2)
            print(f"👤 Чат {chat_id} сохранен для напоминаний.")
    except Exception as e:
        print(f"Error registering subscriber: {e}")

def get_all_subscribers() -> list:
    """Returns list of unique subscriber chat IDs from file and environment."""
    subscribers = []
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                subscribers = json.load(f)
        except Exception:
            subscribers = []
    env_chat = os.getenv("TELEGRAM_USER_CHAT_ID")
    if env_chat:
        try:
            cid = int(env_chat)
            if cid not in subscribers:
                subscribers.append(cid)
        except Exception:
            pass
    return subscribers

def load_workout_tracker() -> dict:
    """Loads state of latest known workout ID and count."""
    if WORKOUT_TRACKER_FILE.exists():
        try:
            with open(WORKOUT_TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_workout_tracker(data: dict):
    """Saves state of latest known workout ID and count."""
    try:
        with open(WORKOUT_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving workout tracker: {e}")

def load_pending_checkin() -> dict:
    """Loads state of pending 20-minute post-workout check-in."""
    if PENDING_CHECKIN_FILE.exists():
        try:
            with open(PENDING_CHECKIN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_pending_checkin(data: dict):
    """Saves state of pending 20-minute post-workout check-in."""
    try:
        with open(PENDING_CHECKIN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving pending checkin: {e}")

@contextmanager
def continuous_typing(bot, chat_id: int):
    """Maintains continuous 'typing...' status in Telegram until response is generated."""
    stop_event = threading.Event()

    def typing_worker():
        while not stop_event.is_set():
            try:
                bot.send_chat_action(chat_id, "typing")
            except Exception:
                pass
            # Telegram typing action expires after ~5 sec; re-trigger every 4 sec
            stop_event.wait(4.0)

    t = threading.Thread(target=typing_worker, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_last = types.KeyboardButton("🏋️ Последняя тренировка")
    b_next = types.KeyboardButton("📋 План на тренировку")
    b_nut_today = types.KeyboardButton("🥗 Питание (сегодня)")
    b_nut_week = types.KeyboardButton("📊 Питание за неделю")
    b_products = types.KeyboardButton("🍽 Что я ел (продукты)")
    b_weekly = types.KeyboardButton("📈 Недельный отчет")
    b_profile = types.KeyboardButton("👤 Мой профиль и вес")
    b_sync = types.KeyboardButton("🔄 Синхронизация")
    keyboard.add(b_last, b_next)
    keyboard.add(b_nut_today, b_nut_week)
    keyboard.add(b_products, b_weekly)
    keyboard.add(b_profile, b_sync)
    return keyboard

def get_system_instruction() -> str:
    """Builds and caches detailed coaching context for Gemini for 10 minutes."""
    now = time.time()
    if _context_cache["instruction"] and (now - _context_cache["timestamp"] < 600):
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

        instruction = f"""
Ты — персональный спортивный тренер и нутрициолог для атлета со следующими параметрами:
- Атлет: Мужчина, Возраст: {age} года (30.06.2004), Рост: {h_cur} см.
- Вес: {w_cur} кг (начальный вес: {start_w} кг, сброшено: {abs(w_cur - start_w):.1f} кг, цель: 80 кг). Идет сушка/похудение с сохранением мышц.
- Тренировочные программы атлета в Hevy (5-дневный сплит):
{routines_context}
- Последняя проведенная тренировка: {last_w_str}.
{recent_feedback_context}- Кардио: бег 3-4 км в темпе ~10 км/ч (в день ног рекомендована ходьба в гору для защиты коленей).
- Питание атлета (YAZIO):
  * Недельный рацион и средние значения:
{weekly_nut_text}
  * Продукты, съеденные сегодня:
{products_text}

Отвечай четко, профессионально, с мотивацией, дружелюбно и строго научно (спортивная биомеханика, гипертрофия, восстановление, подсчет КБЖУ, доказательная база спортивного питания и добавок).
Если атлет спрашивает про средние калории за неделю или что он ел, используй точные реальные цифры и названия продуктов из данных выше.
Если атлет спрашивает про спортивное питание или добавки (креатин, протеин, омега-3, витамин D3, магний, цинк и т.д.), дай развернутый, практичный, безопасный и доказательный совет с учетом его тренировок и похудения.
Отвечай на русском языке.
"""
        _context_cache["instruction"] = instruction
        _context_cache["timestamp"] = now
        return instruction
    except Exception as e:
        print(f"Error building system instruction: {e}")
        return _context_cache["instruction"] or "Ты — персональный спортивный тренер атлета."

def ask_gemini_ai(user_question: str) -> str:
    """Uses Gemini API with cascaded model fallbacks and robust error handling."""
    q_lower = user_question.lower().strip()

    # Fast-path direct handlers for exact button/keyword matches
    if any(w in q_lower for w in ["продукт", "что ел", "что я ел", "меню", "съел"]):
        return coach.get_consumed_products_report()
    if any(w in q_lower for w in ["средн", "недел", "неделя"]) and any(w in q_lower for w in ["калор", "пит", "ед", "бжу", "белок"]):
        return coach.get_weekly_nutrition_report()
    if any(w in q_lower for w in ["план", "след", "что дела"]):
        return coach.preview_next_workout()
    if any(w in q_lower for w in ["послед", "прошл", "тренировк", "как прошл", "тоннаж"]):
        return coach.review_last_workout()
    if any(w in q_lower for w in ["пит", "ед", "калор", "бжу", "белок", "yazio"]) and "недел" not in q_lower:
        return coach.get_nutrition_report()
    if any(w in q_lower for w in ["вес", "профил", "рост", "похудел"]):
        return coach.get_profile_report()
    if any(w in q_lower for w in ["недел", "отчет", "стат", "итог", "таблиц"]) and "пит" not in q_lower:
        return coach.get_sunday_weekly_table_report()

    # Query Gemini models with full fallback cascade
    if GEMINI_KEY:
        try:
            from google import genai
            client = genai.Client(
                api_key=GEMINI_KEY,
                http_options={"timeout": 30_000}  # 30 sec timeout
            )
            system_instruction = get_system_instruction()

            for model_name in MODELS_CASCADE:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"Вопрос атлета: {user_question}",
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

def analyze_post_workout_feedback(user_feedback: str, workout_id: Optional[str] = None) -> str:
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

        prof = {}
        try:
            if coach.yazio.is_configured():
                prof = coach.yazio.get_user_profile() or {}
        except Exception as e:
            print(f"YAZIO profile note in feedback: {e}")
            prof = {}
        w_cur = prof.get("current_weight_kg", 98.1)

        prompt = f"""
Ты — персональный спортивный тренер и физиолог атлета со следующими параметрами:
- Атлет: Мужчина, 22 года, Рост: 182 см, Вес: {w_cur} кг (начальный 103 кг, цель 80 кг, режим: дефицит калорий / сушка с сохранением мышц).
- Атлет только что закончил силовую тренировку и прислал свои ощущения.

РЕАЛЬНЫЕ ДАННЫЕ СЕГОДНЯШНЕЙ ТРЕНИРОВКИ ИЗ HEVY:
- Название программы: {w_title} ({w_date})
- Время тренировки: {duration} мин
- Общий тоннаж: {tonnage:,.0f} кг | Рабочих подходов: {sets_count}
- Выполненные упражнения и подходы:
{exercises_text}
- Кардио: {cardio_text}

ОТВЕТ И СУБЪЕКТИВНЫЕ ОЩУЩЕНИЯ АТЛЕТА:
«{user_feedback}»

ОБЯЗАТЕЛЬНО: В ответе обязательно упомяни любые проблемы, которые пользователь указал в своём тексте (например, боль в спине, тяжело шла тяга, ощущение "забитости" и т.п.).
ТВОЯ ЗАДАЧА:
Проанализируй ощущения атлета, опираясь на спортивную физиологию, биомеханику и его реальные цифры из тренировки выше.
Сформируй структурированный, дружелюбный, ободряющий и научно обоснованный ответ по следующим пунктам:
1. 🎯 Оценка нагрузки и ощущений: свяжи то, что почувствовал атлет, с конкретными весами, количеством подходов или объемом. Объясни, почему организм так отреагировал.
2. 🦴 Суставы, связки и техника: если атлет упомянул дискомфорт или ноющую боль (плечо, колено, локоть, поясница), дай четкие рекомендации по технике (угол локтей, наклон скамьи, разминка манжеты плеча, замена хвата на нейтральный). Если суставы в порядке — похвали технику.
3. ⚡ Восстановление на ближайшие 24-48ч: рекомендации по питанию (белок 30-40г, сложные углеводы, вода/электролиты), сну и расслаблению мышц.
4. 📝 Корректировка следующих тренировок: стоит ли прогрессировать веса, зафиксировать их или скинуть на 5-10% в проблемных упражнениях?

Форматируй текст в Markdown с жирным шрифтом, списками и эмодзи. Ответ должен быть удобен для чтения с мобильного экрана в Telegram. Отвечай на русском языке.
"""

        # Try Gemini models cascade
        if GEMINI_KEY:
            try:
                from google import genai
                from google.genai import types as genai_types
                client = genai.Client(
                    api_key=GEMINI_KEY,
                    http_options={"timeout": 30_000}  # 30 sec timeout
                )
                print(f"[FEEDBACK] Prompt length: {len(prompt)} chars, user_feedback: {user_feedback[:100]}...")
                for model_name in MODELS_CASCADE:
                    try:
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        if resp and resp.text:
                            print(f"[FEEDBACK] Model {model_name} responded OK, length: {len(resp.text)}")
                            return f"📋 *Анализ тренировки и самочувствия:*\n\n{resp.text}"
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
            f"💡 *Разбор тренера:*\n"
            f"1. *Нагрузка*: Суммарный тоннаж {tonnage:,.0f} кг — это солидный силовой объем. Ощущение утомления абсолютно физиологично при сушке и дефиците калорий.\n"
            f"2. *Восстановление*: Закрой потребность в белке (~35–40 г) и выпей 0.7–1.0 л чистой воды с минералами/электролитами в течение ближайшего часа.\n"
            f"3. *Суставы и связки*: При любых признаках дискомфорта удели время качественной разминке перед следующей тренировкой и держи под контролем негативную фазу (2-3 сек опускания снаряда).\n"
            f"4. *Сон*: Не менее 8 часов сна для восстановления нервной системы и снижения кортизола."
        )
    except Exception as err:
        print(f"Error in analyze_post_workout_feedback: {err}")
        return "⚠️ Не удалось сформировать отчет по самочувствию. Попробуй позже."

def dispatch_checkin_if_due(bot, target_chat_id: Optional[int] = None):
    """Dispatches 20-minute post-workout checkin if due."""
    try:
        pending = load_pending_checkin()
        if not pending or pending.get("prompt_sent"):
            return

        due_time = pending.get("due_time", 0)
        now_ts = time.time()
        if now_ts < due_time:
            return

        subscribers = [target_chat_id] if target_chat_id else get_all_subscribers()
        if not subscribers:
            print("⚠️ Опрос готов к отправке, но нет подписчиков. Ожидание сообщения от пользователя...")
            return

        w_title = pending.get("workout_title", "Тренировка")
        w_id = pending.get("workout_id")

        tonnage_str = ""
        for w in coach.workouts:
            if w.get("id") == w_id:
                try:
                    an = coach.analyzer.analyze_workout(w)
                    tonnage_str = f" (сегодняшний тоннаж: {an.get('total_tonnage_kg', 0):,.0f} кг)"
                except Exception:
                    pass
                break

        prompt_text = (
            f"🏋️‍♂️ *Как прошла тренировка «{w_title}»?*{tonnage_str}\n\n"
            f"Прошло около 20 минут после окончания тренировки — самое время зафиксировать ощущения, пока всё свежо в памяти! 🧠\n\n"
            f"💬 *Поделись, как самочувствие:*\n"
            f"1️⃣ *Общее состояние*: легко или тяжело далась тренировка? Хватило ли сил и энергии?\n"
            f"2️⃣ *Рабочие веса*: как зашли подходы? Был ли запас или работал до отказа?\n"
            f"3️⃣ *Суставы и связки*: ничего ли не тянет и не ноет (плечи, локти, колени, поясница)?\n"
            f"4️⃣ *Мышцы*: хороший ли памп или чувствуется сильная скованность/забитость?\n\n"
            f"✍️ *Напиши мне прямо сюда в чат обычным сообщением* свои ощущения — я сопоставлю их с сегодняшними упражнениями и весами, оценю утомление и подскажу, как скорректировать восстановление и следующие нагрузки! 💪"
        )

        sent_count = 0
        for cid in subscribers:
            try:
                bot.send_message(cid, prompt_text, parse_mode="Markdown")
                print(f"📩 Опрос о самочувствии отправлен пользователю {cid}")
                sent_count += 1
            except Exception as err:
                print(f"Не удалось отправить опрос о тренировке в {cid}: {err}")

        if sent_count > 0:
            pending["prompt_sent"] = True
            pending["prompt_sent_time"] = time.time()
            save_pending_checkin(pending)
    except Exception as e:
        print(f"Error in dispatch_checkin_if_due: {e}")

def check_for_new_workouts_and_sync(bot):
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
        end_iso = latest_workout.get("end_time") or latest_workout.get("start_time")

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

            # If newly detected, notify subscribers that sync occurred
            if is_new:
                mins_left = max(0, int((target_due - now_ts) / 60))
                time_hint = f"Примерно через *{mins_left} мин.* я пришлю опрос о твоем самочувствии" if mins_left > 0 else "Через несколько секунд я пришлю опрос о твоем самочувствии"
                msg_text = (
                    f"🔄 *Авто-синхронизация Hevy:* зафиксирована новая тренировка!\n\n"
                    f"🏋️‍♂️ *{w_title}*\n"
                    f"Все упражнения, подходы и веса сохранены в базу.\n\n"
                    f"⏳ {time_hint}, чтобы разобрать нагрузку и восстановление! 💪"
                )
                for cid in get_all_subscribers():
                    try:
                        bot.send_message(cid, msg_text, parse_mode="Markdown")
                    except Exception as err:
                        print(f"Не удалось отправить уведомление об автосинхронизации в {cid}: {err}")

    except Exception as e:
        print(f"Error in check_for_new_workouts_and_sync: {e}")

def run_hevy_auto_sync_monitor(bot):
    """Monitors Hevy API every 90 seconds for newly finished workouts and auto-syncs."""
    def monitor_worker():
        time.sleep(5)
        print("🔄 Фоновый монитор Hevy запущен (автопроверка каждые 90 сек)")
        while True:
            try:
                check_for_new_workouts_and_sync(bot)
            except Exception as e:
                print(f"Auto-sync monitor worker error: {e}")
            time.sleep(90)

    t = threading.Thread(target=monitor_worker, daemon=True)
    t.start()

def run_checkin_dispatcher(bot):
    """Periodically checks if a 20-minute post-workout check-in prompt is due."""
    def dispatcher_worker():
        time.sleep(10)
        print("⏰ Диспетчер опросов после тренировки активен")
        while True:
            try:
                dispatch_checkin_if_due(bot)
            except Exception as e:
                print(f"Check-in dispatcher error: {e}")
            time.sleep(15)

    t = threading.Thread(target=dispatcher_worker, daemon=True)
    t.start()

def run_health_server(bot=None):
    """Lightweight HTTP server for cloud platforms (Render, Koyeb) to keep service active."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int(os.getenv("PORT", 8080))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/debug":
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                try:
                    latest_w = coach.analyzer.get_latest_workout()
                    data = {
                        "subscribers": get_all_subscribers(),
                        "workouts_count": len(coach.workouts),
                        "latest_workout": latest_w.get("title") if latest_w else None,
                        "latest_workout_end": latest_w.get("end_time") if latest_w else None,
                        "tracker": load_workout_tracker(),
                        "pending_checkin": load_pending_checkin()
                    }
                    self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
                except Exception as err:
                    self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))
                return

            if self.path == "/sync_now" and bot:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                try:
                    check_for_new_workouts_and_sync(bot)
                    dispatch_checkin_if_due(bot)
                    self.wfile.write(b'{"status": "ok", "message": "Manual sync and checkin check completed"}')
                except Exception as err:
                    self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))
                return

            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Hevy & YAZIO AI Coach Bot is alive and running 24/7!")

        def log_message(self, format, *args):
            pass

    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"🌐 Health-check HTTP сервер запущен на порту {port}")
    except Exception as e:
        print(f"Health-check server note: {e}")

def run_keep_alive_pinger():
    """Background loop sending HTTP request to public URL every 10 minutes to prevent Render free-tier sleep."""
    import requests

    public_url = os.getenv("RENDER_EXTERNAL_URL", "https://fitness-bot-9f8m.onrender.com")

    def ping_worker():
        time.sleep(30)
        while True:
            try:
                resp = requests.get(public_url, timeout=20)
                print(f"⏰ Self-ping sent to {public_url}: status {resp.status_code}")
            except Exception as e:
                print(f"Self-ping note: {e}")
            time.sleep(600)  # Ping every 10 minutes

    t = threading.Thread(target=ping_worker, daemon=True)
    t.start()
    print(f"⏰ Фоновый keep-alive пингер запущен (интервал 10 мин, цель: {public_url})")

def run_gym_reminder_scheduler(bot):
    """Sends gym reminder Monday to Friday at 10:40 AM (GMT+6)."""
    tz_gmt6 = timezone(timedelta(hours=6))
    last_sent_date = None

    def scheduler_worker():
        nonlocal last_sent_date
        time.sleep(15)
        print("⏰ Планировщик напоминаний в зал активен (Пн–Пт в 10:40 GMT+6)")
        while True:
            try:
                now_gmt6 = datetime.now(tz_gmt6)
                # Monday=0, Friday=4
                if now_gmt6.weekday() < 5 and now_gmt6.hour == 10 and now_gmt6.minute == 40:
                    today_str = now_gmt6.strftime("%Y-%m-%d")
                    if last_sent_date != today_str:
                        subscribers = get_all_subscribers()
                        reminder_text = "👟🎒 *Не забудь сменные вещи в зал и тапочки!*"
                        for cid in subscribers:
                            try:
                                bot.send_message(cid, reminder_text, parse_mode="Markdown")
                                print(f"👟 Напоминание в зал отправлено пользователю {cid}")
                            except Exception as err:
                                print(f"Не удалось отправить напоминание в {cid}: {err}")

                        last_sent_date = today_str
            except Exception as e:
                print(f"Scheduler loop error: {e}")
            time.sleep(20)

    t = threading.Thread(target=scheduler_worker, daemon=True)
    t.start()

def run_sunday_report_scheduler(bot, safe_send_fn):
    """Sends comprehensive weekly summary table every Sunday at 12:00 PM (GMT+6)."""
    tz_gmt6 = timezone(timedelta(hours=6))
    last_sent_date = None

    def scheduler_worker():
        nonlocal last_sent_date
        time.sleep(20)
        print("⏰ Планировщик воскресного отчета активен (каждое Вс в 12:00 GMT+6)")
        while True:
            try:
                now_gmt6 = datetime.now(tz_gmt6)
                # Sunday is 6
                if now_gmt6.weekday() == 6 and now_gmt6.hour == 12 and now_gmt6.minute == 0:
                    today_str = now_gmt6.strftime("%Y-%m-%d")
                    if last_sent_date != today_str:
                        subscribers = get_all_subscribers()
                        if subscribers:
                            try:
                                coach.storage.sync_all(verbose=False)
                                coach.reload(auto_sync=False)
                            except Exception:
                                pass
                            report_text = coach.get_sunday_weekly_table_report()
                            intro_text = (
                                "📊🔔 *Твой воскресный отчет готов!*\n"
                                "Подводим итоги недели: баланс питания, динамика веса и тренировочный тоннаж. 👇\n\n"
                            )
                            full_report = intro_text + report_text
                            for cid in subscribers:
                                try:
                                    safe_send_fn(cid, full_report)
                                    print(f"📊 Воскресный отчет отправлен пользователю {cid}")
                                except Exception as err:
                                    print(f"Не удалось отправить воскресный отчет в {cid}: {err}")
                        last_sent_date = today_str
            except Exception as e:
                print(f"Sunday report scheduler loop error: {e}")
            time.sleep(25)

    t = threading.Thread(target=scheduler_worker, daemon=True)
    t.start()

def start_bot():
    if not TELEGRAM_TOKEN:
        print("⚠️ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env!")
        return

    # Pre-load coach data on startup
    try:
        coach.reload(auto_sync=True)
    except Exception as e:
        print(f"Initial coach load warning: {e}")

    bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")

    run_health_server(bot)
    run_keep_alive_pinger()
    run_gym_reminder_scheduler(bot)
    run_hevy_auto_sync_monitor(bot)
    run_checkin_dispatcher(bot)

    # Initial check on startup: sync new workouts & dispatch any pending checkins immediately
    threading.Thread(
        target=lambda: (time.sleep(2), check_for_new_workouts_and_sync(bot), dispatch_checkin_if_due(bot)),
        daemon=True
    ).start()

    def safe_send(chat_id, text, reply_markup=None):
        chunks = split_message(str(text), max_len=3900)
        last_msg = None
        for i, chunk in enumerate(chunks):
            markup = reply_markup if i == len(chunks) - 1 else None
            try:
                last_msg = bot.send_message(chat_id, chunk, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Markdown send fallback for chunk ({e}), sending as plain text...")
                try:
                    last_msg = bot.send_message(chat_id, chunk, parse_mode=None, reply_markup=markup)
                except Exception as e2:
                    print(f"Failed to send message chunk: {e2}")
        return last_msg

    run_sunday_report_scheduler(bot, safe_send)

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
            w = prof.get("current_weight_kg", 98.8)
            text = (
                f"Привет, атлет! 🏋️‍♂️\n\n"
                f"Я твой персональный ИИ-тренер, подключенный к твоим аккаунтам *Hevy* и *YAZIO*.\n\n"
                f"Твои параметры: *{w} кг* | *182 см* | Цель: *80 кг*.\n\n"
                f"🔥 *Что работает автоматически:*\n"
                f"• 🔄 *Авто-синхронизация Hevy*: я каждые 90 сек отслеживаю завершение тренировок и сам обновляю базу.\n"
                f"• 💬 *Опрос через 20 минут*: через ~20 мин после тренировки я напишу тебе, узнаю о самочувствии и сопоставлю твои ощущения с весами и тоннажем!\n"
                f"• 🔔 *Напоминание в зал*: Пн–Пт в 10:40 утра (GMT+6).\n"
                f"• 📊 *Воскресный отчет*: каждое воскресенье в 12:00 дня (GMT+6) сводная таблица КБЖУ, тоннаж тренировок и динамика веса.\n\n"
                f"Используй кнопки внизу для быстрого доступа, команды `/test_sunday_report`, `/test_checkin`, `/myid` или просто напиши мне любой вопрос в чат!"
            )
            safe_send(message.chat.id, text, reply_markup=get_main_keyboard())
        dispatch_checkin_if_due(bot, message.chat.id)

    @bot.message_handler(commands=['myid', 'id'])
    def handle_my_id(message):
        register_subscriber(message.chat.id)
        text = (
            f"👤 *Твой Telegram Chat ID:* `{message.chat.id}`\n\n"
            f"✅ Ты успешно зарегистрирован в списке подписчиков бота для напоминаний и опросов после тренировок!\n\n"
            f"💡 *Совет для 100% надежности на Render:*\n"
            f"В панели Render в настройках сервиса в разделе *Environment Variables* добавь:\n"
            f"• Ключ: `TELEGRAM_USER_CHAT_ID`\n"
            f"• Значение: `{message.chat.id}`\n\n"
            f"Тогда сервер никогда не забудет твой чат даже при любых перезагрузках сервиса."
        )
        safe_send(message.chat.id, text, reply_markup=get_main_keyboard())
        dispatch_checkin_if_due(bot, message.chat.id)

    @bot.message_handler(commands=['test_reminder'])
    def handle_test_reminder(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            reminder_text = (
                "👟🎒 *Не забудь сменные вещи в зал и тапочки!*\n\n"
                "_(Это тестовая проверка напоминания. Автоматически оно будет приходить с понедельника по пятницу ровно в 10:40 утра по твоему времени GMT+6)_"
            )
            safe_send(message.chat.id, reminder_text, reply_markup=get_main_keyboard())

    @bot.message_handler(commands=['test_checkin', 'checkin'])
    def handle_test_checkin(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            latest = coach.analyzer.get_latest_workout()
            if not latest:
                safe_send(message.chat.id, "⚠️ Тренировок пока не найдено. Нажми '🔄 Синхронизация'.", reply_markup=get_main_keyboard())
                return

            an = coach.analyzer.analyze_workout(latest)
            w_title = an.get("title", "Тренировка")
            tonnage = an.get("total_tonnage_kg", 0)

            pending = {
                "workout_id": latest.get("id"),
                "workout_title": w_title,
                "end_time": latest.get("end_time"),
                "due_time": time.time() - 1,
                "prompt_sent": True,
                "prompt_sent_time": time.time(),
                "responded": False
            }
            save_pending_checkin(pending)

            prompt_text = (
                f"🏋️‍♂️ *Как прошла тренировка «{w_title}»?* (сегодняшний тоннаж: {tonnage:,.0f} кг)\n\n"
                f"_(Тестовый запуск опроса самочувствия. В боевом режиме бот присылает его автоматически через 20 минут после окончания тренировки в Hevy)_\n\n"
                f"💬 *Поделись своими ощущениями:*\n"
                f"1️⃣ *Общее состояние*: легко или тяжело далась тренировка? Хватило ли сил и энергии?\n"
                f"2️⃣ *Рабочие веса*: как зашли подходы? Был ли запас или работал до отказа?\n"
                f"3️⃣ *Суставы и связки*: ничего ли не тянет и не ноет (плечи, локти, колени, поясница)?\n"
                f"4️⃣ *Мышцы*: хороший ли памп или чувствуется сильная скованность/забитость?\n\n"
                f"✍️ *Напиши мне прямо сейчас в ответ любое сообщение* со своими мыслями — я проанализирую твои слова вместе с сегодняшними весами и тоннажем, оценю утомление и подскажу, как скорректировать восстановление и следующие нагрузки! 💪"
            )
            safe_send(message.chat.id, prompt_text, reply_markup=get_main_keyboard())

    @bot.message_handler(commands=['feedback'])
    def handle_feedback_command(message):
        register_subscriber(message.chat.id)
        feedback_text = message.text.replace("/feedback", "", 1).strip()
        if not feedback_text:
            safe_send(
                message.chat.id,
                "ℹ️ Напиши свой отзыв о последней тренировке после команды, например:\n`/feedback Тяжело пошел жим гантелей, правое плечо немного ныло, трицепс забился`",
                reply_markup=get_main_keyboard()
            )
            return

        with continuous_typing(bot, message.chat.id):
            feedback_report = analyze_post_workout_feedback(feedback_text)
            safe_send(message.chat.id, feedback_report, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🏋️ Последняя тренировка" or msg.text == "/last")
    def handle_last(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.review_last_workout()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📋 План на тренировку" or msg.text == "/next")
    def handle_next(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.preview_next_workout()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text in ["🥗 Питание (сегодня)", "🥗 Питание (YAZIO)"] or msg.text in ["/today", "/nutrition"])
    def handle_nutrition(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_nutrition_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📊 Питание за неделю" or msg.text == "/week_nutrition")
    def handle_week_nutrition(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_weekly_nutrition_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🍽 Что я ел (продукты)" or msg.text == "/products")
    def handle_products(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_consumed_products_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(commands=['sunday_report', 'test_sunday_report'])
    def handle_sunday_report_cmd(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_sunday_weekly_table_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📈 Недельный отчет" or msg.text == "/weekly")
    def handle_weekly(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_sunday_weekly_table_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "👤 Мой профиль и вес" or msg.text == "/profile")
    def handle_profile(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.get_profile_report()
            safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🔄 Синхронизация" or msg.text == "/sync")
    def handle_sync(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            # Invalidate context cache
            _context_cache["timestamp"] = 0
            sync_res = coach.storage.sync_all(verbose=False)
            coach.reload(auto_sync=False)
            check_for_new_workouts_and_sync(bot)
            text = f"✅ *Данные синхронизированы!*\n\n• Загружено тренировок: *{sync_res['workouts_count']}*\n• Программ тренировок: *{sync_res['routines_count']}*"
            safe_send(message.chat.id, text, reply_markup=get_main_keyboard())
        dispatch_checkin_if_due(bot, message.chat.id)

    @bot.message_handler(func=lambda msg: True)
    def handle_free_text(message):
        register_subscriber(message.chat.id)

        # Check if user is responding to pending post-workout check-in
        pending = load_pending_checkin()
        if pending and pending.get("prompt_sent") and not pending.get("responded"):
            prompt_sent_time = pending.get("prompt_sent_time", 0)
            # Accept within 8 hours of prompt
            if time.time() - prompt_sent_time < 8 * 3600 and not message.text.startswith("/"):
                q_lower = message.text.lower().strip()
                is_pure_nutrition_query = (
                    any(w in q_lower for w in ["что ел", "что я ел", "меню", "сколько калор"]) and
                    not any(w in q_lower for w in ["болит", "тяжел", "легк", "плеч", "спин", "мышц", "устал", "жим", "вес", "тренировк", "самочувств"])
                )
                if not is_pure_nutrition_query:
                    with continuous_typing(bot, message.chat.id):
                        try:
                            feedback_report = analyze_post_workout_feedback(message.text, pending.get("workout_id"))
                            safe_send(message.chat.id, feedback_report, reply_markup=get_main_keyboard())
                            # Mark as responded ONLY after successful send
                            pending["responded"] = True
                            pending["last_user_feedback"] = message.text
                            pending["last_feedback_time"] = time.time()
                            save_pending_checkin(pending)
                        except Exception as fb_err:
                            print(f"Feedback analysis send error: {fb_err}")
                            safe_send(message.chat.id, "⚠️ Произошла ошибка при анализе. Попробуй написать ещё раз!", reply_markup=get_main_keyboard())
                    return

        with continuous_typing(bot, message.chat.id):
            reply = ask_gemini_ai(message.text)
            safe_send(message.chat.id, reply, reply_markup=get_main_keyboard())

    print("🤖 Telegram бот запущен и слушает входящие сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)

if __name__ == "__main__":
    start_bot()
