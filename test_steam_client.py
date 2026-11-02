import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from fastapi import HTTPException
from steam_client import get_played_games, DEFAULT_STEAM_ID


class SteamClientTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'STEAM_API_KEY': 'test-secret', 'STEAM_ID': DEFAULT_STEAM_ID})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def fetch(self, payload):
        with patch('steam_client.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            return get_played_games()

    def test_strict_threshold_and_duplicate_appids(self):
        games = [{'appid': i, 'name': f'Game {i}', 'playtime_forever': minutes}
                 for i, minutes in enumerate([0, 299, 300, 301, 600], 1)]
        steam_id, result = self.fetch({'response': {'game_count': 5, 'games': games + [games[-1]]}})
        self.assertEqual(steam_id, DEFAULT_STEAM_ID)
        self.assertEqual([game['minutes'] for game in result], [301, 600])

    def test_empty_library_is_valid_but_private_or_malformed_is_error(self):
        self.assertEqual(self.fetch({'response': {'game_count': 0}})[1], [])
        for payload in ({'response': {}}, {'response': {'game_count': 3}},
                        {'response': {'game_count': 1, 'games': [{'appid': 1, 'name': 'Hidden'}]}},
                        {'response': {'game_count': 1, 'games': [{'appid': 1, 'name': 'Bad', 'playtime_forever': 'oops'}]}}):
            with self.assertRaises(HTTPException):
                self.fetch(payload)

    def test_missing_key_never_calls_steam(self):
        with patch.dict(os.environ, {'STEAM_API_KEY': ''}), patch('steam_client.urllib.request.urlopen') as request:
            with self.assertRaises(HTTPException) as error:
                get_played_games()
            self.assertEqual(error.exception.status_code, 503)
            request.assert_not_called()

    def test_upstream_error_does_not_expose_key(self):
        error = urllib.error.HTTPError('https://steam.test/?key=test-secret', 403, 'Forbidden', {}, None)
        with patch('steam_client.urllib.request.urlopen', side_effect=error):
            with self.assertRaises(HTTPException) as caught:
                get_played_games()
            self.assertNotIn('test-secret', caught.exception.detail)
            self.assertEqual(caught.exception.status_code, 502)


if __name__ == '__main__':
    unittest.main()
