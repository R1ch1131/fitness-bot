import os
import sys
import telebot
from telebot import types
from datetime import datetime, date

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import API_KEY as HEVY_KEY
from coach import AIHevyCoach

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

coach = AIHevyCoach(auto_sync=False)

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_last = types.KeyboardButton("🏋️ Последняя тренировка")
    b_next = types.KeyboardButton("📋 План на тренировку")
    b_nutrition = types.KeyboardButton("🥗 Питание (YAZIO)")
    b_weekly = types.KeyboardButton("📈 Недельный отчет")
    b_profile = types.KeyboardButton("👤 Мой профиль и вес")
    b_sync = types.KeyboardButton("🔄 Синхронизация")
    keyboard.add(b_last, b_next)
    keyboard.add(b_nutrition, b_weekly)
    keyboard.add(b_profile, b_sync)
    return keyboard

def ask_gemini_ai(user_question: str) -> str:
    """Uses Gemini API with full training & nutrition context if key is available, with smart rule-based fallback."""
    q_lower = user_question.lower().strip()

    # Smart intent recognition (works always, even without Gemini key)
    if any(w in q_lower for w in ["план", "след", "что дела", "сегодня", "упражнен"]):
        return coach.preview_next_workout()
    if any(w in q_lower for w in ["послед", "прошл", "тренировк", "как прошл", "тоннаж"]):
        return coach.review_last_workout()
    if any(w in q_lower for w in ["пит", "ед", "калор", "бжу", "белок", "углевод", "yazio", "язио"]):
        return coach.get_nutrition_report()
    if any(w in q_lower for w in ["вес", "профил", "рост", "похудел", "параметр"]):
        return coach.get_profile_report()
    if any(w in q_lower for w in ["недел", "отчет", "стат", "сводк"]):
        return coach.weekly_overview()
    if any(w in q_lower for w in ["синхр", "обнов"]):
        sync_res = coach.storage.sync_all(verbose=False)
        return f"✅ Данные обновлены!\nЗагружено тренировок: {sync_res['workouts_count']}\nПрограмм: {sync_res['routines_count']}"

    if not GEMINI_KEY:
        return (
            "💬 Тренер на связи!\n\n"
            f"Я вижу твой вопрос: «{user_question}».\n\n"
            "Ты можешь писать мне текстом простые команды: *«план на сегодня»*, *«как прошла тренировка»*, *«что с питанием»*, *«мой вес»*, или нажимать кнопки меню.\n\n"
            "🧠 **Хочешь, чтобы я рассуждал и отвечал на любые сложные вопросы?**\n"
            "Получи бесплатный ключ Gemini за 20 секунд на [aistudio.google.com/apikey](https://aistudio.google.com/apikey) и добавь его как `GEMINI_API_KEY` в настройки бота!"
        )

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)

        # Context compilation
        prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
        w_cur = prof.get("current_weight_kg", 99.3)
        h_cur = prof.get("height_cm", 182)
        age = prof.get("age", 22)
        start_w = prof.get("start_weight_kg", 103.0)

        # Recent nutrition
        try:
            nut = coach.yazio.get_daily_summary() if coach.yazio.is_configured() else {}
        except Exception:
            nut = {}

        system_instruction = f"""
Ты — персональный спортивный тренер и нутрициолог для атлета со следующими параметрами:
- Пол: Мужской, Возраст: {age} года (30.06.2004), Рост: {h_cur} см.
- Текущий вес: {w_cur} кг (начальный вес: {start_w} кг, цель: 80 кг). Идет сушка/похудение с сохранением мышц.
- Тренировочный сплит (Hevy): 5 дней в неделю (Пн: Push/Жим, Вт: Pull/Спина, Ср: Legs 1, Чт: Upper, Пт: Legs 2/Становая).
- Кардио: бег 3-4 км в темпе ~10 км/ч (в дни ног рекомендована ходьба в гору для защиты коленей).
- Питание (YAZIO): целевой белок 160-200 г (1.6-2.0 г/кг). Сейчас потребление ~1700-2000 ккал.

Отвечай четко, профессионально, с мотивацией, дружелюбно и строго научно (спортивная биомеханика, гипертрофия, восстановление).
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Вопрос атлета: {user_question}",
            config={"system_instruction": system_instruction}
        )
        return response.text
    except Exception as e:
        return f"Не удалось связаться с Gemini AI: {e}"

def run_health_server():
    """Lightweight HTTP server for cloud platforms (Render, Koyeb) to keep service active."""
    import threading
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

def start_bot():
    if not TELEGRAM_TOKEN:
        print("⚠️ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env!")
        print("Получите токен у @BotFather в Telegram и пропишите его в .env: TELEGRAM_BOT_TOKEN=ваш_токен")
        return

    run_health_server()
    bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        text = (
            f"Привет, атлет! 🏋️‍♂️\n\n"
            f"Я твой персональный ИИ-тренер, подключенный к твоим аккаунтам **Hevy** и **YAZIO**.\n\n"
            f"Твои текущие параметры: **{coach.yazio.get_user_profile().get('current_weight_kg', 99.3)} кг** | **182 см** | Цель: **80 кг**.\n\n"
            f"Используй кнопки внизу для быстрого доступа или просто напиши мне любой вопрос!"
        )
        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🏋️ Последняя тренировка" or msg.text == "/last")
    def handle_last(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.review_last_workout()
        bot.send_message(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📋 План на тренировку" or msg.text == "/next")
    def handle_next(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.preview_next_workout()
        bot.send_message(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🥗 Питание (YAZIO)" or msg.text == "/today")
    def handle_nutrition(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_nutrition_report()
        bot.send_message(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📈 Недельный отчет" or msg.text == "/weekly")
    def handle_weekly(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.weekly_overview()
        bot.send_message(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "👤 Мой профиль и вес" or msg.text == "/profile")
    def handle_profile(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_profile_report()
        bot.send_message(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🔄 Синхронизация" or msg.text == "/sync")
    def handle_sync(message):
        bot.send_chat_action(message.chat.id, "typing")
        sync_res = coach.storage.sync_all(verbose=False)
        text = f"✅ Данные обновлены!\nЗагружено тренировок: {sync_res['workouts_count']}\nПрограмм (сплитов): {sync_res['routines_count']}"
        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: True)
    def handle_free_text(message):
        bot.send_chat_action(message.chat.id, "typing")
        reply = ask_gemini_ai(message.text)
        bot.send_message(message.chat.id, reply, reply_markup=get_main_keyboard())

    print("🤖 Telegram бот запущен и слушает входящие сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)

if __name__ == "__main__":
    start_bot()
