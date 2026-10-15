import os
import json
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from coach import AIHevyCoach
from storage import Storage
from analyzer import WorkoutAnalyzer
from config import BASE_DIR, DATA_DIR, WORKOUTS_CACHE_FILE, ROUTINES_CACHE_FILE

from habits_manager import HabitsManager
from books_manager import BooksManager

# Initialize Coach singleton
coach = AIHevyCoach(auto_sync=False)
habits_mgr = HabitsManager()
books_mgr = BooksManager()

app = FastAPI(title="Hevy & YAZIO AI Coach PWA", version="1.0.0")

# Enable CORS for local dev (Vite running on localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TZ_GMT6 = timezone(timedelta(hours=6))

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

class ToggleHabitRequest(BaseModel):
    habit_id: str
    date: str

class CreateHabitRequest(BaseModel):
    title: str
    category: str
    target_days: Optional[int] = 7

class EditHabitRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    target_days: Optional[int] = None

class CreateBookRequest(BaseModel):
    title: str
    author: str
    category: Optional[str] = "Саморазвитие"
    total_pages: Optional[int] = 300
    status: Optional[str] = "reading"
    current_page: Optional[int] = 0
    rating: Optional[float] = None
    notes: Optional[str] = None

class UpdateBookRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    rating: Optional[float] = None
    notes: Optional[str] = None

class ReadingSessionRequest(BaseModel):
    pages_read: int

@app.get("/api/health")
@app.get("/health")
def health():
    return {"status": "ok", "app": "Hevy & YAZIO AI Coach PWA"}

@app.get("/status")
def status_endpoint():
    try:
        from bot import load_workout_tracker, load_pending_checkin
        latest_w = coach.analyzer.get_latest_workout() if coach.analyzer else None
        return {
            "status": "online",
            "workouts_count": len(coach.workouts),
            "latest_workout": latest_w.get("title") if latest_w else None,
            "latest_workout_end": latest_w.get("end_time") if latest_w else None,
            "tracker": load_workout_tracker(),
            "pending_checkin": load_pending_checkin()
        }
    except Exception as e:
        return {"status": "online", "note": str(e)}

@app.get("/logs")
def logs_endpoint():
    try:
        from bot import RECENT_LOGS
        return "\n".join(list(RECENT_LOGS)) if RECENT_LOGS else "No logs recorded yet."
    except Exception as e:
        return f"Logs unavailable: {e}"

@app.get("/api/dashboard")
def get_dashboard():
    """Returns today's nutrition, next workout, weight status and recent weight trend."""
    # Auto-sync habits from Hevy and YAZIO
    try:
        habits_mgr.sync_with_hevy_and_yazio(coach)
    except Exception as e:
        print(f"Habit auto-sync in dashboard note: {e}")

    now_gmt6 = datetime.now(TZ_GMT6)
    today_date = now_gmt6.date()
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today_weekday = weekdays_ru[now_gmt6.weekday()]

    # 1. Nutrition for today from YAZIO
    nutrition_data = {
        "calories": 0.0,
        "calories_goal": 2000.0,
        "protein": 0.0,
        "protein_goal": 160.0,
        "carbs": 0.0,
        "fat": 0.0,
        "water_ml": 0,
        "meals": {}
    }

    try:
        daily_summary = coach.yazio.get_daily_summary(today_date)
        nutrition_data["calories"] = float(daily_summary.get("calories", 0.0))
        nutrition_data["protein"] = float(daily_summary.get("protein", 0.0))
        nutrition_data["fat"] = float(daily_summary.get("fat", 0.0))
        nutrition_data["carbs"] = float(daily_summary.get("carbs", 0.0))
        nutrition_data["water_ml"] = int(daily_summary.get("water_ml", 0))
    except Exception as e:
        print(f"Dashboard summary fetch error: {e}")

    try:
        consumed = coach.yazio.get_consumed_products(today_date)
        nutrition_data["meals"] = consumed.get("meals", {})
    except Exception as e:
        print(f"Dashboard consumed products fetch error: {e}")

    # 2. Workout status from Hevy
    workout_data = {
        "today_completed": False,
        "today_workout": None,
        "next_routine": None
    }

    try:
        # Check if today has a completed workout in Hevy
        today_str = today_date.strftime("%Y-%m-%d")
        for w in coach.workouts:
            w_start = w.get("start_time", "")
            if w_start.startswith(today_str):
                workout_data["today_completed"] = True
                an = WorkoutAnalyzer([w])
                workout_data["today_workout"] = an.analyze_workout(w)
                break

        # Get next scheduled routine
        last_w = coach.analyzer.get_latest_workout()
        last_title = last_w.get("title", "").strip().lower() if last_w else ""
        routine_order = ["понедельник", "вторник", "среда", "четверг", "пятница"]
        next_name = "понедельник"
        for i, name in enumerate(routine_order):
            if name in last_title:
                next_name = routine_order[(i + 1) % len(routine_order)]
                break

        target_r = None
        for r in coach.routines:
            if next_name in r.get("title", "").lower():
                target_r = r
                break
        if not target_r and coach.routines:
            target_r = coach.routines[0]

        if target_r:
            ex_list = []
            for ex in target_r.get("exercises", []):
                t = coach.translate_exercise_title(ex.get("title", ""), template_id=ex.get("exercise_template_id"))
                ex_list.append({
                    "title": t,
                    "target_sets": len(ex.get("sets", [])),
                    "target_reps": "8-12",
                    "last_weight": "По плану"
                })
            workout_data["next_routine"] = {
                "routine_title": target_r.get("title", ""),
                "exercises": ex_list
            }
    except Exception as e:
        print(f"Dashboard workout fetch error: {e}")

    # 3. Weight and profile
    profile_data = {
        "current_weight": 96.0,
        "start_weight": 103.0,
        "goal_weight": 80.0,
        "weight_history": []
    }

    try:
        prof = coach.yazio.get_user_profile()
        profile_data["current_weight"] = prof.get("current_weight", 96.0)
        profile_data["start_weight"] = prof.get("start_weight", 103.0)
        profile_data["goal_weight"] = prof.get("goal_weight", 80.0)
    except Exception as e:
        print(f"Profile fetch error: {e}")

    # Weight history (past 14 days)
    try:
        from yazio_exporter.export_body import fetch_weight_range
        start_d = (today_date - timedelta(days=14)).strftime("%Y-%m-%d")
        end_d = today_date.strftime("%Y-%m-%d")
        w_map = coach.yazio._execute_with_retry(fetch_weight_range, coach.yazio.client, start_d, end_d)
        sorted_weights = sorted(
            [{"date": k, "weight": round(v, 2)} for k, v in w_map.items()],
            key=lambda x: x["date"]
        )
        profile_data["weight_history"] = sorted_weights
    except Exception as e:
        print(f"Weight history fetch error: {e}")

    weekdays_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    today_weekday_short = weekdays_short[now_gmt6.weekday()]
    monday = today_date - timedelta(days=now_gmt6.weekday())
    week_dates = {
        weekdays_short[i]: (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    }

    return {
        "date": today_date.strftime("%Y-%m-%d"),
        "date_formatted": today_date.strftime("%d.%m.%Y"),
        "weekday": today_weekday,
        "weekday_short": today_weekday_short,
        "time": now_gmt6.strftime("%H:%M"),
        "week_dates": week_dates,
        "nutrition": nutrition_data,
        "workout": workout_data,
        "profile": profile_data
    }

@app.get("/api/workouts")
def get_workouts():
    """Returns cached workout history and available routines."""
    analyzed_workouts = []
    for w in coach.workouts[:15]:
        analyzed = coach.analyzer.analyze_workout(w)
        analyzed_workouts.append(analyzed)

    routines = []
    for r in coach.routines:
        exercises = []
        for ex in r.get("exercises", []):
            raw_title = ex.get("title", "")
            tid = ex.get("exercise_template_id")
            ru_title = coach.translate_exercise_title(raw_title, template_id=tid)
            exercises.append({
                "title": ru_title,
                "sets_count": len(ex.get("sets", []))
            })
        routines.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "exercises": exercises
        })

    return {
        "workouts": analyzed_workouts,
        "routines": routines
    }

@app.get("/api/weekly")
def get_weekly():
    """Returns weekly nutrition and workout summary."""
    try:
        report_text = coach.get_sunday_weekly_table_report()
        nutrition_weekly = coach.yazio.get_weekly_nutrition()
        return {
            "report_markdown": report_text,
            "days": nutrition_weekly.get("days", []),
            "averages": nutrition_weekly.get("averages", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync")
def sync_data():
    """Forces sync with Hevy and YAZIO."""
    try:
        res = coach.storage.sync_all(verbose=False)
        coach.reload(auto_sync=False)
        habits_mgr.sync_with_hevy_and_yazio(coach)
        return {"status": "ok", "synced": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/habits")
def get_habits():
    """Returns active habits with dynamic consecutive streaks and history."""
    try:
        habits = habits_mgr.sync_with_hevy_and_yazio(coach)
    except Exception as e:
        print(f"Habits sync error: {e}")
        habits = habits_mgr.get_habits()
    return {
        "habits": habits,
        "today_summary": habits_mgr.get_habits_ai_summary()
    }

@app.post("/api/habits/toggle")
def toggle_habit(req: ToggleHabitRequest):
    """Toggles completion of habit for given date and updates streak."""
    try:
        updated = habits_mgr.toggle_day(req.habit_id, req.date)
        return {"status": "ok", "habit": updated, "habits": habits_mgr.get_habits()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/habits")
def create_habit(req: CreateHabitRequest):
    """Creates a new habit in tracker."""
    try:
        h = habits_mgr.add_habit(req.title, req.category, req.target_days or 7)
        return {"status": "ok", "habit": h, "habits": habits_mgr.get_habits()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/habits/{habit_id}")
def delete_habit(habit_id: str):
    """Deletes habit from tracker."""
    habits_mgr.delete_habit(habit_id)
    return {"status": "ok", "habits": habits_mgr.get_habits()}

@app.put("/api/habits/{habit_id}")
def edit_habit(habit_id: str, req: EditHabitRequest):
    """Edits habit details."""
    try:
        h = habits_mgr.edit_habit(habit_id, req.title, req.category, req.target_days)
        return {"status": "ok", "habit": h, "habits": habits_mgr.get_habits()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chat")
def chat_with_coach(req: ChatRequest):
    """Processes messages to AI coach with full real-time athlete context and habits."""
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Refresh habits sync so AI has 100% up-to-date state
    try:
        habits_mgr.sync_with_hevy_and_yazio(coach)
    except Exception as e:
        print(f"Habit sync in chat note: {e}")

    try:
        from bot import ask_gemini_ai
        ai_reply = ask_gemini_ai(user_msg, force_llm=True)
        return {"reply": ai_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation error: {str(e)}")

# ==================== BOOKS / LIBRARY ENDPOINTS ====================

@app.get("/api/books")
def get_books():
    """Returns library books and reading stats."""
    return {
        "books": books_mgr.get_books(),
        "stats": books_mgr.get_stats()
    }

@app.post("/api/books")
def create_book(req: CreateBookRequest):
    """Creates a new book in athlete's library."""
    try:
        b = books_mgr.add_book(
            title=req.title,
            author=req.author,
            category=req.category or "Саморазвитие",
            total_pages=req.total_pages or 300,
            status=req.status or "reading",
            current_page=req.current_page or 0,
            rating=req.rating,
            notes=req.notes
        )
        return {"status": "ok", "book": b, "books": books_mgr.get_books(), "stats": books_mgr.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/books/{book_id}")
def update_book(book_id: str, req: UpdateBookRequest):
    """Updates book progress, rating, notes, or reading status."""
    try:
        b = books_mgr.update_book(
            book_id=book_id,
            title=req.title,
            author=req.author,
            category=req.category,
            status=req.status,
            current_page=req.current_page,
            total_pages=req.total_pages,
            rating=req.rating,
            notes=req.notes
        )
        return {
            "status": "ok",
            "book": b,
            "books": books_mgr.get_books(),
            "stats": books_mgr.get_stats(),
            "habits": habits_mgr.get_habits()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/books/{book_id}/progress")
def record_reading_session(book_id: str, req: ReadingSessionRequest):
    """Logs pages read today, updates book, and auto-marks reading habit."""
    try:
        b = books_mgr.record_reading_session(book_id, req.pages_read)
        return {
            "status": "ok",
            "book": b,
            "books": books_mgr.get_books(),
            "stats": books_mgr.get_stats(),
            "habits": habits_mgr.get_habits()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/books/{book_id}")
def delete_book(book_id: str):
    """Removes a book from the library."""
    books_mgr.delete_book(book_id)
    return {"status": "ok", "books": books_mgr.get_books(), "stats": books_mgr.get_stats()}

class SyncBooksPayload(BaseModel):
    books: List[Dict[str, Any]]

class RestoreBackupPayload(BaseModel):
    books: Optional[List[Dict[str, Any]]] = None
    habits: Optional[List[Dict[str, Any]]] = None

@app.post("/api/books/sync_all")
def sync_all_books(req: SyncBooksPayload):
    """Syncs/restores full library from client-side persistent storage."""
    try:
        if req.books:
            books_mgr._save(req.books)
        return {"status": "ok", "books": books_mgr.get_books(), "stats": books_mgr.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/backup")
def get_backup():
    """Exports full JSON backup of athlete's library and habits."""
    return {
        "timestamp": datetime.now(TZ_GMT6).isoformat(),
        "books": books_mgr.get_books(),
        "habits": habits_mgr.get_habits()
    }

@app.post("/api/restore")
def restore_backup(req: RestoreBackupPayload):
    """Restores library and habits from JSON backup."""
    if req.books is not None:
        books_mgr._save(req.books)
    if req.habits is not None:
        habits_mgr._save(req.habits)
    return {
        "status": "ok",
        "books": books_mgr.get_books(),
        "stats": books_mgr.get_stats(),
        "habits": habits_mgr.get_habits()
    }

# Mount static frontend files if built
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
