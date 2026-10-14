import json
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import DATA_DIR
from habits_manager import HabitsManager, TZ_GMT6

BOOKS_FILE = DATA_DIR / "books.json"

DEFAULT_BOOKS = [
    {
        "id": "book-1",
        "title": "Атомные привычки",
        "author": "Джеймс Клир",
        "category": "Продуктивность",
        "status": "finished",
        "current_page": 304,
        "total_pages": 304,
        "rating": 5,
        "notes": "Маленькие изменения на 1% каждый день дают феноменальный кумулятивный результат. Фокус на системе, а не на сиюминутной цели.",
        "finished_date": "2026-09-20",
        "created_at": "2026-09-01"
    },
    {
        "id": "book-2",
        "title": "Грокаем алгоритмы",
        "author": "Адитья Бхаргава",
        "category": "IT / Код",
        "status": "finished",
        "current_page": 288,
        "total_pages": 288,
        "rating": 5,
        "notes": "Наглядное понимание алгоритмической сложности Big O, бинарного поиска, рекурсии и графов с алгоритмом Дейкстры.",
        "finished_date": "2026-10-02",
        "created_at": "2026-09-15"
    },
    {
        "id": "book-3",
        "title": "Дисциплина — это судьба",
        "author": "Райан Холидей",
        "category": "Саморазвитие",
        "status": "reading",
        "current_page": 140,
        "total_pages": 350,
        "rating": 5,
        "notes": "Самоконтроль — это не лишение себя радостей, а фундамент подлинной свободы и уверенности.",
        "finished_date": None,
        "created_at": "2026-10-05"
    }
]

class BooksManager:
    def __init__(self):
        self.file_path = BOOKS_FILE
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_BOOKS, f, ensure_ascii=False, indent=2)

    def get_books(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_BOOKS

    def get_stats(self) -> Dict[str, Any]:
        books = self.get_books()
        finished = [b for b in books if b.get("status") == "finished"]
        reading = [b for b in books if b.get("status") == "reading"]
        planned = [b for b in books if b.get("status") == "planned"]
        
        total_pages = sum(b.get("current_page", 0) for b in books)
        return {
            "total": len(books),
            "finished": len(finished),
            "reading": len(reading),
            "planned": len(planned),
            "total_pages_read": total_pages
        }

    def add_book(
        self,
        title: str,
        author: str,
        category: str = "Саморазвитие",
        total_pages: int = 300,
        status: str = "reading",
        current_page: int = 0,
        rating: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        books = self.get_books()
        now_str = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")
        
        new_book = {
            "id": f"book-{str(uuid.uuid4())[:8]}",
            "title": title.strip(),
            "author": author.strip(),
            "category": category.strip() or "Саморазвитие",
            "status": status,
            "current_page": current_page,
            "total_pages": max(1, total_pages),
            "rating": rating,
            "notes": notes.strip() if notes else None,
            "finished_date": now_str if status == "finished" else None,
            "created_at": now_str
        }
        books.append(new_book)
        self._save(books)
        return new_book

    def update_book(
        self,
        book_id: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None,
        rating: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        books = self.get_books()
        target = None
        for b in books:
            if b.get("id") == book_id:
                target = b
                break

        if not target:
            raise ValueError(f"Book with id {book_id} not found")

        old_page = target.get("current_page", 0)
        old_status = target.get("status")

        if title is not None:
            target["title"] = title.strip()
        if author is not None:
            target["author"] = author.strip()
        if category is not None:
            target["category"] = category.strip()
        if total_pages is not None:
            target["total_pages"] = max(1, total_pages)
        if rating is not None:
            target["rating"] = rating
        if notes is not None:
            target["notes"] = notes.strip()

        now_str = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")

        if current_page is not None:
            target["current_page"] = min(target.get("total_pages", 9999), max(0, current_page))
            # Auto-mark habit if reading progress increased
            if target["current_page"] - old_page >= 10:
                self._mark_reading_habit_for_today()

        if status is not None:
            target["status"] = status
            if status == "finished" and old_status != "finished":
                target["finished_date"] = now_str
                target["current_page"] = target.get("total_pages", target.get("current_page", 0))
                self._mark_reading_habit_for_today()

        self._save(books)
        return target

    def record_reading_session(self, book_id: str, pages_read: int) -> Dict[str, Any]:
        """Adds pages_read to current_page and auto-closes reading habit."""
        books = self.get_books()
        target = None
        for b in books:
            if b.get("id") == book_id:
                target = b
                break

        if not target:
            raise ValueError(f"Book with id {book_id} not found")

        cur = target.get("current_page", 0)
        tot = target.get("total_pages", 300)
        new_page = min(tot, cur + pages_read)
        target["current_page"] = new_page

        if new_page >= tot:
            target["status"] = "finished"
            target["finished_date"] = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")

        # Automatically mark reading habit for today if pages >= 10
        if pages_read >= 10:
            self._mark_reading_habit_for_today()

        self._save(books)
        return target

    def _mark_reading_habit_for_today(self):
        """Marks the reading habit as True for today in habits_manager."""
        try:
            hm = HabitsManager()
            habits = hm.get_habits()
            today_str = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")
            for h in habits:
                if h.get("id") == "reading" or "чтени" in h.get("title", "").lower():
                    hist = h.setdefault("history", {})
                    hist[today_str] = True
                    hm._save(habits)
                    break
        except Exception as e:
            print(f"Auto-mark reading habit error: {e}")

    def delete_book(self, book_id: str) -> bool:
        books = self.get_books()
        books = [b for b in books if b.get("id") != book_id]
        self._save(books)
        return True

    def _save(self, books: List[Dict[str, Any]]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(books, f, ensure_ascii=False, indent=2)

    def get_library_ai_summary(self) -> str:
        """Formats library contents into clean summary for Gemini context."""
        books = self.get_books()
        if not books:
            return "Библиотека пока пуста."

        finished = [b for b in books if b.get("status") == "finished"]
        reading = [b for b in books if b.get("status") == "reading"]
        planned = [b for b in books if b.get("status") == "planned"]

        lines = [f"📚 Библиотека атлета (Всего: {len(books)}, Прочитано: {len(finished)}):"]
        
        if reading:
            lines.append("📖 СЕЙЧАС ЧИТАЕТ:")
            for b in reading:
                prog = f"{b.get('current_page', 0)}/{b.get('total_pages', '?')} стр."
                lines.append(f"  • «{b['title']}» ({b['author']}) — {b.get('category')}, прогресс: {prog}")

        if finished:
            lines.append("🏆 ПРОЧИТАННЫЕ КНИГИ:")
            for b in finished:
                rate_str = f" ⭐ {b['rating']}/5" if b.get('rating') else ""
                note_str = f" | Инсайт: «{b['notes']}»" if b.get('notes') else ""
                lines.append(f"  • «{b['title']}» ({b['author']}){rate_str}{note_str}")

        if planned:
            lines.append("📌 В ПЛАНАХ НА ЧТЕНИЕ:")
            for b in planned:
                lines.append(f"  • «{b['title']}» ({b['author']}) — {b.get('category')}")

        return "\n".join(lines)
