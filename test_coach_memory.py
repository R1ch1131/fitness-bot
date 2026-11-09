import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import coach_memory as memory
from cloud_storage import CloudStorageError


class CoachMemoryTests(unittest.TestCase):
    def test_cloud_memory_survives_empty_chat_history_and_enters_prompt(self):
        cloud = {}
        def write(key, value):
            cloud[key] = value
            return True
        with patch.object(memory, 'is_cloud_configured', return_value=True), \
             patch.object(memory, 'set_cloud_data', side_effect=write), \
             patch.object(memory, 'get_cloud_data', side_effect=lambda key, **kw: cloud.get(key)):
            memory.save_memory('  Изучаю JavaScript  ')
            write('athlete_chat_history', [])
            self.assertEqual(memory.read_memory()['text'], 'Изучаю JavaScript')
            self.assertIn('Изучаю JavaScript', memory.ai_context())
            memory.save_memory('')
            self.assertEqual(memory.ai_context(), '')

    def test_cloud_failure_does_not_claim_saved_or_fall_back_to_local(self):
        with patch.object(memory, 'is_cloud_configured', return_value=True), \
             patch.object(memory, 'set_cloud_data', return_value=False):
            with self.assertRaises(CloudStorageError):
                memory.save_memory('Факт')
        with patch.object(memory, 'is_cloud_configured', return_value=True), \
             patch.object(memory, 'get_cloud_data', side_effect=CloudStorageError('offline')):
            with self.assertRaises(CloudStorageError):
                memory.read_memory()
            self.assertIn('недоступна', memory.ai_context())

    def test_local_storage_and_size_validation(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(memory, 'FILE', Path(directory) / 'memory.json'), \
             patch.object(memory, 'is_cloud_configured', return_value=False):
            self.assertEqual(memory.read_memory()['text'], '')
            memory.save_memory('Учусь')
            self.assertEqual(memory.read_memory()['text'], 'Учусь')
            with self.assertRaises(ValueError):
                memory.save_memory('a' * 10001)
            self.assertEqual(memory.read_memory()['text'], 'Учусь')


if __name__ == '__main__':
    unittest.main()
