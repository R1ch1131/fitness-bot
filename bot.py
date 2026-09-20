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
    """Uses Gemini API with full training & nutrition context, falling back to smart intent recognition."""
    q_lower = user_question.lower().strip()

    # If Gemini key is available, pass conversational questions directly to Gemini!
    if GEMINI_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_KEY)

            # Ensure data is loaded
            if not coach.workouts or not coach.routines:
                coach.reload(auto_sync=True)

            prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
            w_cur = prof.get("current_weight_kg", 98.8)
            h_cur = prof.get("height_cm", 182)
            age = prof.get("age", 22)
            start_w = prof.get("start_weight_kg", 103.0)

            # Routines overview for Gemini context
            routines_context = ""
            for r in coach.routines:
                ex_names = ", ".join([coach.translate_exercise_title(e.get("title", ""), e.get("exercise_template_id")) for e in r.get("exercises", [])])
                routines_context += f"- {r.get('title')}: {ex_names}\n"

            # Last workout overview
            last_w = coach.analyzer.get_latest_workout()
            last_w_str = f"{last_w.get('title')} ({last_w.get('start_time')})" if last_w else "нет записей"

            system_instruction = f"""
Ты — персональный спортивный тренер и нутрициолог для атлета со следующими параметрами:
- Атлет: Мужчина, Возраст: {age} года (30.06.2004), Рост: {h_cur} см.
- Вес: {w_cur} кг (начальный вес: {start_w} кг, цель: 80 кг). Идет сушка/похудение с сохранением мышц.
- Тренировочные программы атлета в Hevy (5-дневный сплит):
{routines_context}
- Последняя проведенная тренировка: {last_w_str}.
- Кардио: бег 3-4 км в темпе ~10 км/ч (в день ног рекомендована ходьба в гору для защиты коленей).
- Питание (YAZIO): норма белка 160-200 г (1.6-2.0 г/кг). Сейчас среднее потребление ~1700-2000 ккал.

Отвечай четко, профессионально, с мотивацией, дружелюбно и строго научно (спортивная биомеханика, гипертрофия, восстановление).
Если атлет спрашивает про конкретный день (например, понедельник), подробно разбери его упражнения из его программы выше, дай советы по технике, весам и разминке.
Отвечай на русском языке.
"""
            for model_name in ["gemini-3.6-flash", "gemini-2.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"Вопрос атлета: {user_question}",
                        config={"system_instruction": system_instruction}
                    )
                    return response.text
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini API error: {e}")

    # Fallback to direct handlers if Gemini is unavailable
    if any(w in q_lower for w in ["план", "след", "что дела"]):
        return coach.preview_next_workout()
    if any(w in q_lower for w in ["послед", "прошл", "тренировк", "как прошл", "тоннаж"]):
        return coach.review_last_workout()
    if any(w in q_lower for w in ["пит", "ед", "калор", "бжу", "белок", "yazio"]):
        return coach.get_nutrition_report()
    if any(w in q_lower for w in ["вес", "профил", "рост", "похудел"]):
        return coach.get_profile_report()
    if any(w in q_lower for w in ["недел", "отчет", "стат"]):
        return coach.weekly_overview()

    return "Я на связи! Напиши свой вопрос о тренировках или питании, или выбери действие в меню ниже."

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
        return

    # Pre-load coach data on startup
    try:
        coach.reload(auto_sync=True)
    except Exception as e:
        print(f"Initial coach load warning: {e}")

    run_health_server()
    bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")

    def safe_send(chat_id, text, reply_markup=None):
        try:
            return bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception as e:
            print(f"Markdown send fallback ({e}), sending as plain text...")
            return bot.send_message(chat_id, text, parse_mode=None, reply_markup=reply_markup)

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
        w = prof.get("current_weight_kg", 98.8)
        text = (
            f"Привет, атлет! 🏋️‍♂️\n\n"
            f"Я твой персональный ИИ-тренер, подключенный к твоим аккаунтам *Hevy* и *YAZIO*.\n\n"
            f"Твои параметры: *{w} кг* | *182 см* | Цель: *80 кг*.\n\n"
            f"Используй кнопки внизу для быстрого доступа или просто напиши мне любой вопрос в чат!"
        )
        safe_send(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🏋️ Последняя тренировка" or msg.text == "/last")
    def handle_last(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.review_last_workout()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📋 План на тренировку" or msg.text == "/next")
    def handle_next(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.preview_next_workout()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🥗 Питание (YAZIO)" or msg.text == "/today")
    def handle_nutrition(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_nutrition_report()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📈 Недельный отчет" or msg.text == "/weekly")
    def handle_weekly(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.weekly_overview()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "👤 Мой профиль и вес" or msg.text == "/profile")
    def handle_profile(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_profile_report()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🔄 Синхронизация" or msg.text == "/sync")
    def handle_sync(message):
        bot.send_chat_action(message.chat.id, "typing")
        sync_res = coach.storage.sync_all(verbose=False)
        coach.reload(auto_sync=False) # Reload into memory!
        text = f"✅ *Данные синхронизированы!*\n\n• Загружено тренировок: *{sync_res['workouts_count']}*\n• Программ тренировок: *{sync_res['routines_count']}*"
        safe_send(message.chat.id, text, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: True)
    def handle_free_text(message):
        bot.send_chat_action(message.chat.id, "typing")
        reply = ask_gemini_ai(message.text)
        safe_send(message.chat.id, reply, reply_markup=get_main_keyboard())

    print("🤖 Telegram бот запущен и слушает входящие сообщения...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)

if __name__ == "__main__":
    start_bot()
