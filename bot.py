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

# Cache for Gemini system instruction to avoid repetitive heavy YAZIO queries on every message
_context_cache = {
    "timestamp": 0,
    "instruction": ""
}

# Reliable active Gemini models in priority order
MODELS_CASCADE = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest"
]

def register_subscriber(chat_id: int):
    """Saves user chat_id for scheduled gym reminders."""
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

        instruction = f"""
Ты — персональный спортивный тренер и нутрициолог для атлета со следующими параметрами:
- Атлет: Мужчина, Возраст: {age} года (30.06.2004), Рост: {h_cur} см.
- Вес: {w_cur} кг (начальный вес: {start_w} кг, сброшено: {abs(w_cur - start_w):.1f} кг, цель: 80 кг). Идет сушка/похудение с сохранением мышц.
- Тренировочные программы атлета в Hevy (5-дневный сплит):
{routines_context}
- Последняя проведенная тренировка: {last_w_str}.
- Кардио: бег 3-4 км в темпе ~10 км/ч (в день ног рекомендована ходьба в гору для защиты коленей).
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
    if any(w in q_lower for w in ["недел", "отчет", "стат"]) and "пит" not in q_lower:
        return coach.weekly_overview()

    # Query Gemini models with full fallback cascade
    if GEMINI_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_KEY)
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

def run_health_server():
    """Lightweight HTTP server for cloud platforms (Render, Koyeb) to keep service active."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int(os.getenv("PORT", 8080))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
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
                        subscribers = []
                        if SUBSCRIBERS_FILE.exists():
                            try:
                                with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                                    subscribers = json.load(f)
                            except Exception:
                                subscribers = []

                        env_chat = os.getenv("TELEGRAM_USER_CHAT_ID")
                        if env_chat and int(env_chat) not in subscribers:
                            subscribers.append(int(env_chat))

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

def start_bot():
    if not TELEGRAM_TOKEN:
        print("⚠️ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env!")
        return

    # Pre-load coach data on startup
    try:
        coach.reload(auto_sync=True)
    except Exception as e:
        print(f"Initial coach load warning: {e}")

    run_health_server()
    run_keep_alive_pinger()

    bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")
    run_gym_reminder_scheduler(bot)

    def safe_send(chat_id, text, reply_markup=None):
        try:
            return bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception as e:
            print(f"Markdown send fallback ({e}), sending as plain text...")
            return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

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
                f"🔔 *Авто-напоминание в зал*: включено с Пн по Пт в 10:40 утра (GMT+6).\n\n"
                f"Используй кнопки внизу для быстрого доступа или просто напиши мне любой вопрос в чат!"
            )
            safe_send(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(commands=['test_reminder'])
    def handle_test_reminder(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            reminder_text = (
                "👟🎒 *Не забудь сменные вещи в зал и тапочки!*\n\n"
                "_(Это тестовая проверка напоминания. Автоматически оно будет приходить с понедельника по пятницу ровно в 10:40 утра по твоему времени GMT+6)_"
            )
            safe_send(message.chat.id, reminder_text, reply_markup=get_main_keyboard())

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

    @bot.message_handler(func=lambda msg: msg.text == "📈 Недельный отчет" or msg.text == "/weekly")
    def handle_weekly(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            res = coach.weekly_overview()
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
            text = f"✅ *Данные синхронизированы!*\n\n• Загружено тренировок: *{sync_res['workouts_count']}*\n• Программ тренировок: *{sync_res['routines_count']}*"
            safe_send(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: True)
    def handle_free_text(message):
        register_subscriber(message.chat.id)
        with continuous_typing(bot, message.chat.id):
            reply = ask_gemini_ai(message.text)
            safe_send(message.chat.id, reply, reply_markup=get_main_keyboard())

    print("🤖 Telegram бот запущен и слушает входящие сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)

if __name__ == "__main__":
    start_bot()
