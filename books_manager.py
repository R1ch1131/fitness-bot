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
        "current_page": 155,
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
        try:
            from cloud_storage import get_cloud_data
            cloud_books = get_cloud_data("athlete_books")
            if cloud_books and isinstance(cloud_books, list):
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(cloud_books, f, ensure_ascii=False, indent=2)
                return
        except Exception as ce:
            print(f"Cloud check note in books_manager: {ce}")

        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_BOOKS, f, ensure_ascii=False, indent=2)

    def get_books(self) -> List[Dict[str, Any]]:
        needs_save = False
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                books = json.load(f)
        except Exception:
            books = DEFAULT_BOOKS
            needs_save = True

        # Data integrity / repair pass
        for b in books:
            b["total_pages"] = max(1, int(b.get("total_pages") or 300))
            if b.get("status") == "finished":
                # Finished book has read 100% of pages
                if b.get("current_page", 0) < b["total_pages"]:
                    b["current_page"] = b["total_pages"]
                    needs_save = True
            elif b.get("status") == "planned":
                b["current_page"] = 0
            else:
                b["current_page"] = max(0, int(b.get("current_page") or 0))

        if needs_save:
            try:
                self._save(books)
            except Exception:
                pass

        return books

    def get_stats(self) -> Dict[str, Any]:
        books = self.get_books()
        finished = [b for b in books if b.get("status") == "finished"]
        reading = [b for b in books if b.get("status") == "reading"]
        planned = [b for b in books if b.get("status") == "planned"]
        
        # Accurately compute pages read: finished books count full total_pages, reading books count current_page
        total_pages_read = sum(
            b.get("total_pages", 0) if b.get("status") == "finished"
            else b.get("current_page", 0)
            for b in books
        )
        library_total_pages = sum(b.get("total_pages", 0) for b in books)

        return {
            "total": len(books),
            "finished": len(finished),
            "reading": len(reading),
            "planned": len(planned),
            "total_pages_read": total_pages_read,
            "library_total_pages": library_total_pages
        }

    def add_book(
        self,
        title: str,
        author: str,
        category: str = "Саморазвитие",
        total_pages: int = 300,
        status: str = "reading",
        current_page: Optional[int] = None,
        rating: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        books = self.get_books()
        now_str = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")
        
        valid_total_pages = max(1, int(total_pages or 300))
        
        if status == "finished":
            final_current_page = valid_total_pages
            final_finished_date = now_str
        elif status == "planned":
            final_current_page = 0
            final_finished_date = None
        else:
            # reading
            parsed_cur = int(current_page) if current_page is not None else 0
            final_current_page = min(valid_total_pages, max(0, parsed_cur))
            final_finished_date = None
            if final_current_page >= valid_total_pages and valid_total_pages > 0:
                status = "finished"
                final_finished_date = now_str

        new_book = {
            "id": f"book-{str(uuid.uuid4())[:8]}",
            "title": title.strip(),
            "author": author.strip(),
            "category": category.strip() or "Саморазвитие",
            "status": status,
            "current_page": final_current_page,
            "total_pages": valid_total_pages,
            "rating": rating,
            "notes": notes.strip() if notes else None,
            "finished_date": final_finished_date,
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
        now_str = datetime.now(TZ_GMT6).strftime("%Y-%m-%d")

        if title is not None:
            target["title"] = title.strip()
        if author is not None:
            target["author"] = author.strip()
        if category is not None:
            target["category"] = category.strip()
        if total_pages is not None:
            target["total_pages"] = max(1, int(total_pages))
        if rating is not None:
            target["rating"] = rating
        if notes is not None:
            target["notes"] = notes.strip() if notes else None

        tot = target.get("total_pages", 300)

        if current_page is not None:
            parsed_cur = max(0, int(current_page))
            target["current_page"] = min(tot, parsed_cur)
            # Auto-mark habit if reading progress increased by >= 10 pages
            if target["current_page"] - old_page >= 10:
                self._mark_reading_habit_for_today()

        if status is not None:
            target["status"] = status
            if status == "finished":
                target["finished_date"] = target.get("finished_date") or now_str
                target["current_page"] = tot
                self._mark_reading_habit_for_today()
            elif status == "planned":
                target["finished_date"] = None
                target["current_page"] = 0

        # Auto-complete if current page reached total pages
        if target.get("current_page", 0) >= tot and target.get("status") == "reading":
            target["status"] = "finished"
            target["finished_date"] = now_str
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
        new_page = min(tot, max(0, cur + pages_read))
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
        try:
            from cloud_storage import set_cloud_data
            set_cloud_data("athlete_books", books)
        except Exception:
            pass

    def get_library_ai_summary(self) -> str:
        """Formats library contents into clean summary for Gemini context."""
        books = self.get_books()
        if not books:
            return "Библиотека пока пуста."

        finished = [b for b in books if b.get("status") == "finished"]
        reading = [b for b in books if b.get("status") == "reading"]
        planned = [b for b in books if b.get("status") == "planned"]

        total_pages_read = sum(
            b.get("total_pages", 0) if b.get("status") == "finished"
            else b.get("current_page", 0)
            for b in books
        )
        total_lib_pages = sum(b.get("total_pages", 0) for b in books)

        lines = [f"📚 Библиотека атлета (Всего книг: {len(books)}, Прочитано: {len(finished)}, Всего прочитано страниц: {total_pages_read} из {total_lib_pages} стр.):"]
        
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
                lines.append(f"  • «{b['title']}» ({b['author']}) ({b.get('total_pages', 0)} стр.){rate_str}{note_str}")

        if planned:
            lines.append("📌 В ПЛАНАХ НА ЧТЕНИЕ:")
            for b in planned:
                lines.append(f"  • «{b['title']}» ({b['author']}) — {b.get('category')} (~{b.get('total_pages', 0)} стр.)")

        return "\n".join(lines)
