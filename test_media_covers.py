import base64
import io
import unittest
from unittest.mock import patch

from PIL import Image
from media_covers import normalize_cover, find_covers


class CoverTests(unittest.TestCase):
    def test_upload_is_small_and_survives_editing_without_recompression(self):
        data = io.BytesIO()
        Image.new('RGB', (1800, 1000), '#446688').save(data, 'PNG')
        value = normalize_cover('data:image/png;base64,' + base64.b64encode(data.getvalue()).decode())
        self.assertTrue(value.startswith('data:image/webp;base64,'))
        raw = base64.b64decode(value.split(',')[1])
        self.assertLessEqual(len(raw), 55000)
        with Image.open(io.BytesIO(raw)) as picture:
            self.assertLessEqual(picture.width, 720)
            self.assertLessEqual(picture.height, 400)
        self.assertEqual(normalize_cover(value), value)

    def test_valid_catalog_cover_and_explicit_removal(self):
        cover = 'https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg'
        self.assertEqual(normalize_cover(cover), cover)
        self.assertIsNone(normalize_cover(None))
        for invalid in ('data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,broken', 'https://not-steam.test/a.jpg'):
            with self.assertRaises(ValueError):
                normalize_cover(invalid)

    def test_search_does_not_need_key_or_import_a_game(self):
        with patch('media_covers.urllib.request.urlopen', return_value=io.BytesIO(b'{"items":[{"id":620,"name":"Portal 2"}]}')), \
             patch('media_covers._store', return_value={'header_image': 'https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg'}):
            result = find_covers('Portal 2')
        self.assertEqual(result['results'][0]['title'], 'Portal 2')
        self.assertTrue(result['results'][0]['image'].endswith('/620/header.jpg'))

    def test_new_games_use_actual_hashed_artwork_and_can_fall_back_to_search_image(self):
        payload = b'{"items":[{"id":4115450,"name":"Phantom Blade Zero","tiny_image":"https://shared.akamai.steamstatic.com/assets/small.jpg"}]}'
        artwork = 'https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/4115450/hash/header.jpg'
        with patch('media_covers.urllib.request.urlopen', return_value=io.BytesIO(payload)), \
             patch('media_covers._store', return_value={'header_image': artwork}):
            self.assertEqual(find_covers('Phantom Blade Zero')['results'][0]['image'], artwork)
        with patch('media_covers.urllib.request.urlopen', return_value=io.BytesIO(payload)), \
             patch('media_covers._store', return_value=None):
            self.assertTrue(find_covers('Phantom Blade Zero')['results'][0]['image'].endswith('/small.jpg'))


if __name__ == '__main__':
    unittest.main()
