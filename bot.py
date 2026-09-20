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

            # Weekly nutrition context
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

            # Consumed products context
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

            system_instruction = f"""
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

Отвечай четко, профессионально, с мотивацией, дружелюбно и строго научно (спортивная биомеханика, гипертрофия, восстановление, подсчет КБЖУ).
Если атлет спрашивает про средние калории за неделю или что он ел, используй точные реальные цифры и названия продуктов из данных выше.
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
    if any(w in q_lower for w in ["продукт", "что ел", "что я ел", "меню", "съел"]):
        return coach.get_consumed_products_report()
    if any(w in q_lower for w in ["средн", "недел", "неделя"]) and any(w in q_lower for w in ["калор", "пит", "ед", "бжу", "белок"]):
        return coach.get_weekly_nutrition_report()
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

def run_keep_alive_pinger():
    """Background loop sending HTTP request to public URL every 10 minutes to prevent Render free-tier sleep."""
    import time
    import threading
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

    @bot.message_handler(func=lambda msg: msg.text in ["🥗 Питание (сегодня)", "🥗 Питание (YAZIO)"] or msg.text in ["/today", "/nutrition"])
    def handle_nutrition(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_nutrition_report()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📊 Питание за неделю" or msg.text == "/week_nutrition")
    def handle_week_nutrition(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_weekly_nutrition_report()
        safe_send(message.chat.id, res, reply_markup=get_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🍽 Что я ел (продукты)" or msg.text == "/products")
    def handle_products(message):
        bot.send_chat_action(message.chat.id, "typing")
        res = coach.get_consumed_products_report()
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
