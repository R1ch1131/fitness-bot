"""Fresh daily facts and reading progress for a personalized, spoiler-free review."""
import json
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=6))


def recent_checkin(pending, now=None):
    if not pending:
        return False
    now = now or datetime.now(TZ).timestamp()
    due = pending.get("due_time")
    return isinstance(due, (int, float)) and -3600 <= now - due <= 8 * 3600


def is_workout_checkin(message, pending=None, now=None):
    text = message.casefold()
    explicit = any(s in text for s in ("закончил тренировку", "закончила тренировку", "отзыв о тренировке",
                                       "самочувствие после тренировки", "разбери мою тренировку"))
    if explicit:
        return True
    if not pending or pending.get("responded"):
        return False
    if not recent_checkin(pending, now):
        return False
    workout = any(s in text for s in ("трениров", "подход", "гантел", "штанг", "станов", "присед", "жим", "тяг", "выпад"))
    unrelated = any(s in text for s in ("рецепт", "съесть", "калори", "питани", "сон", "книг", "страниц", "python", "код", "программ"))
    feelings = any(s in text for s in ("устал", "самочув", "болит", "боль", "тяжел", "тяжёл", "легко", "нормально", "чувствую", "забит"))
    if unrelated and not feelings:
        return False
    return workout or (feelings and not unrelated)


def reading_comment(book, reading_done=None):
    total = max(1, int(book.get("total_pages") or 1))
    page = min(total, max(0, int(book.get("current_page") or 0)))
    # No LLM and no external book knowledge: page numbers cannot identify plot boundaries.
    line = f"Книга «{book['title']}»: {page}/{total} стр. ({round(page / total * 100)}%), осталось {total - page}."
    if reading_done is True:
        line += " Чтение на сегодня отмечено."
    return line


def collect_daily_review(coach, habits=None, books=None, now=None):
    today = (now or datetime.now(TZ)).astimezone(TZ).date()
    facts = {"date": today.isoformat(), "timezone": "Asia/Omsk"}
    reading_done = None
    try:
        if habits is None:
            from habits_manager import HabitsManager
            habits = HabitsManager()
            habits.sync_with_hevy_and_yazio(coach)
        done, unchecked, weekly = [], [], []
        for habit in habits.get_habits():
            checked = bool(habit.get("history", {}).get(today.isoformat()))
            if habit.get("id") == "reading":
                reading_done = checked
            if habit.get("id") == "gym" and today.weekday() >= 5 and not checked:
                continue
            title = str(habit.get("title", "Без названия"))[:160]
            if checked:
                done.append(title)
            elif habit.get("id") == "gym" or habit.get("target_days", 7) == 7:
                unchecked.append(title)
            else:
                weekly.append({"title": title, "target_days": habit.get("target_days")})
        facts.update(completed=done, not_marked_today=unchecked, weekly_targets=weekly)
    except Exception:
        facts["habits_status"] = "unavailable"
    try:
        if coach.yazio.is_configured():
            daily = coach.yazio.get_daily_summary(today) or {}
            if daily.get("calories", 0) > 0 or daily.get("protein", 0) > 0:
                facts["nutrition"] = {key: daily.get(key) for key in ("calories", "protein", "fat", "carbs")}
                facts["nutrition"]["goals"] = {key: value for key, value in daily.get("goals", {}).items()
                                                if key in ("calories", "protein", "fat", "carbs")}
    except Exception:
        facts["nutrition_status"] = "unavailable"
    comment = ""
    try:
        if books is None:
            from books_manager import BooksManager
            books = BooksManager()
        current = next((book for book in books.get_books() if book.get("status") == "reading"), None)
        if current:
            comment = reading_comment(current, reading_done)
            # Only bibliographic facts: arbitrary notes may contain unknown plot details.
            total = max(1, int(current.get("total_pages") or 1))
            page = min(total, max(0, int(current.get("current_page") or 0)))
            facts["reading"] = {
                "title": str(current.get("title", ""))[:300],
                "author": str(current.get("author", ""))[:200],
                "current_page": page, "total_pages": total,
                "percent": round(page / total * 100), "marked_today": reading_done,
            }
    except Exception:
        facts["library_status"] = "unavailable"
    # The fallback keeps a deterministic progress line; successful AI replies use the reading facts.
    return json.dumps(facts, ensure_ascii=False), comment
