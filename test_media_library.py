import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from media_library import MediaLibrary, router


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'media.json'
        self.manager = MediaLibrary(self.path)
        self.patches = [patch('media_library.library', self.manager),
                        patch('media_library.get_cloud_data', return_value=None),
                        patch('media_library.set_cloud_data', return_value=True)]
        self.mocks = [p.start() for p in self.patches]
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_crud_survives_reload_and_deletion_stays_empty(self):
        self.assertEqual(self.client.get('/api/media').json(), {'items': []})
        for kind in ('game', 'movie', 'series', 'anime'):
            response = self.client.post('/api/media', json={'title': f'  {kind}  ', 'kind': kind})
            self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(MediaLibrary(self.path).items()), 4)
        game = items[0]
        response = self.client.put('/api/media/' + game['id'], json={
            'title': 'Пройдено', 'kind': 'game', 'progress': 100, 'rating': 8.5, 'notes': 'Финал'})
        updated = response.json()['items'][0]
        self.assertEqual((updated['status'], updated['total'], updated['notes']), ('finished', 100, 'Финал'))
        self.assertEqual(updated['created_at'], game['created_at'])
        for item in items:
            self.assertEqual(self.client.delete('/api/media/' + item['id']).status_code, 200)
        self.assertEqual(MediaLibrary(self.path).items(), [])
        self.mocks[2].assert_called_with('athlete_media', [])
        self.assertEqual(self.client.delete('/api/media/missing').status_code, 404)

    def test_series_progress_and_completion(self):
        response = self.client.post('/api/media', json={'title': 'Аниме', 'kind': 'anime', 'progress': 3})
        item = response.json()['items'][0]
        self.assertEqual((item['status'], item['total']), ('active', None))
        response = self.client.put('/api/media/' + item['id'], json={
            'title': 'Аниме', 'kind': 'anime', 'progress': 3, 'total': 12, 'status': 'finished'})
        self.assertEqual(response.json()['items'][0]['progress'], 12)

    def test_invalid_input_cannot_modify_collection(self):
        for payload in ({'title': ' ', 'kind': 'game'}, {'title': 'x', 'kind': 'other'},
                        {'title': 'x', 'kind': 'game', 'progress': 101},
                        {'title': 'x', 'kind': 'anime', 'progress': 13, 'total': 12},
                        {'title': 'x', 'kind': 'movie', 'rating': 11},
                        {'title': 'x', 'kind': 'series', 'progress': -1}):
            self.assertEqual(self.client.post('/api/media', json=payload).status_code, 422)
        self.assertEqual(self.client.get('/api/media').json()['items'], [])
        self.assertEqual(self.client.put('/api/media/missing', json={'title': 'x', 'kind': 'movie'}).status_code, 404)

    def test_cloud_recovery_including_empty_collection(self):
        self.client.post('/api/media', json={'title': 'Old', 'kind': 'movie'})
        self.mocks[1].return_value = []
        self.assertEqual(MediaLibrary(self.path).items(), [])


if __name__ == '__main__':
    unittest.main()
