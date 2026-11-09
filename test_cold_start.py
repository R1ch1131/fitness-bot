import ast
import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import app_runtime

class ColdStartTests(unittest.TestCase):
    def test_launcher_has_no_telegram_dependency(self):
        source = Path('bot.py').read_text(encoding='utf-8')
        self.assertNotIn('telebot', source)
        self.assertNotIn('TELEGRAM', source)
        ast.parse(Path('trainer_runtime.py').read_text(encoding='utf-8'))
        self.assertNotIn('telebot', Path('requirements.txt').read_text().lower())

    def test_startup_never_waits_for_external_sync(self):
        with patch.object(app_runtime, '_started', False), patch.object(app_runtime.threading, 'Thread') as thread:
            app_runtime.start_background_services()
            app_runtime.start_background_services()
            self.assertEqual(thread.call_count, 2)
            self.assertEqual(thread.return_value.start.call_count, 2)

    def test_scheduler_key_only_accepts_scoped_credential(self):
        key = 'a' * 40
        derived = hashlib.sha256(('fitpulse-scheduler-v1\0' + key).encode()).hexdigest()
        with patch.dict(os.environ, {'HEALTH_IMPORT_TOKEN': key}):
            self.assertTrue(app_runtime.authorize_scheduler('Bearer ' + derived))
            self.assertFalse(app_runtime.authorize_scheduler('Bearer ' + key))
            self.assertFalse(app_runtime.authorize_scheduler(None))

if __name__ == '__main__':
    unittest.main()
