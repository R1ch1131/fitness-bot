import copy
import unittest
from unittest.mock import Mock
from books_manager import BooksManager


class BookProgressTests(unittest.TestCase):
    def manager(self):
        manager = BooksManager.__new__(BooksManager)
        book = {'id': 'test', 'title': 'Test', 'status': 'reading', 'current_page': 282, 'total_pages': 384}
        manager.get_books = lambda: [copy.deepcopy(book)]
        manager._save = Mock()
        manager._mark_reading_habit_for_today = Mock()
        return manager

    def test_only_reaching_final_page_completes_reading(self):
        manager = self.manager()
        self.assertEqual(manager.update_book('test', current_page=383)['status'], 'reading')
        completed = manager.update_book('test', current_page=384)
        self.assertEqual(completed['status'], 'finished')
        self.assertTrue(completed['finished_date'])
        self.assertEqual(manager.record_reading_session('test', 102)['status'], 'finished')

    def test_status_shortcut_cannot_finish_an_unread_book(self):
        for page in [None, 282, 383]:
            manager = self.manager()
            with self.assertRaises(ValueError):
                manager.update_book('test', status='finished', current_page=page)
            manager._save.assert_not_called()
            manager._mark_reading_habit_for_today.assert_not_called()

    def test_reading_status_clears_old_completion_date(self):
        manager = self.manager()
        manager.get_books = lambda: [{'id': 'test', 'status': 'reading', 'current_page': 282, 'total_pages': 384, 'finished_date': '2026-10-27'}]
        self.assertIsNone(manager.update_book('test', status='reading')['finished_date'])


if __name__ == '__main__':
    unittest.main()
