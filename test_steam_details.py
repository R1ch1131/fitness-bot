import os
import unittest
from unittest.mock import patch

import steam_details as details


class DetailsTests(unittest.TestCase):
    def setUp(self):
        details._cache.clear()
        self.env = patch.dict(os.environ, {'STEAM_API_KEY': 'secret-key'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        details._cache.clear()

    def upstream(self, url):
        if 'appdetails' in url:
            return {'620': {'success': True, 'data': {
                'short_description': 'A <b>great</b> game &amp; more',
                'header_image': 'https://shared.akamai.steamstatic.com/game.jpg',
                'genres': [{'description': 'Puzzle'}], 'developers': ['Valve'],
                'screenshots': [{'path_full': 'https://evil.test/track.jpg'}]}}}
        if 'GetPlayerAchievements' in url:
            return {'playerstats': {'success': True, 'achievements': [
                {'apiname': 'ONE', 'achieved': 1, 'unlocktime': 120},
                {'apiname': 'HIDDEN', 'achieved': 0, 'unlocktime': 0}]}}
        return {'game': {'availableGameStats': {'achievements': [
            {'name': 'ONE', 'displayName': 'Done', 'description': 'Win', 'icon': 'https://cdn.akamai.steamstatic.com/one.jpg'},
            {'name': 'HIDDEN', 'displayName': 'Spoiler', 'hidden': 1, 'description': 'Spoiler text'},
            {'name': 'THREE', 'displayName': 'Still ahead', 'hidden': 0}]}}}

    def test_summary_icons_hidden_achievements_and_cache(self):
        with patch('steam_details._fetch_json', side_effect=self.upstream) as fetch:
            result = details.get_game_details(620, '123')
            self.assertEqual(result['store']['description'], 'A great game & more')
            self.assertEqual(result['store']['screenshots'], [])
            progress = result['achievements']
            self.assertEqual((progress['state'], progress['unlocked'], progress['total']), ('ready', 1, 3))
            self.assertEqual(progress['entries'][0]['name'], 'Done')
            hidden = next(entry for entry in progress['entries'] if entry['id'] == 'HIDDEN')
            self.assertEqual((hidden['name'], hidden['description']), ('Скрытое достижение', ''))
            self.assertNotIn('secret-key', str(result))
            details.get_game_details(620, '123')
            self.assertEqual(fetch.call_count, 3)

    def test_without_key_store_artwork_still_works(self):
        with patch.dict(os.environ, {'STEAM_API_KEY': ''}), patch('steam_details._fetch_json', side_effect=self.upstream) as fetch:
            result = details.get_game_details(620, '123')
            self.assertTrue(result['store']['header_image'])
            self.assertEqual(result['achievements'], {'state': 'no_key'})
            self.assertEqual(fetch.call_count, 1)

    def test_unavailable_stats_are_not_shown_as_zero_achievements(self):
        def partial(url):
            if 'GetPlayerAchievements' in url:
                return {'playerstats': {'success': False}}
            return self.upstream(url)
        with patch('steam_details._fetch_json', side_effect=partial):
            result = details.get_game_details(620, '123')
            self.assertIsNotNone(result['store'])
            self.assertEqual(result['achievements'], {'state': 'unavailable'})

    def test_network_failure_is_safe_and_retryable(self):
        with patch('steam_details._fetch_json', side_effect=OSError('secret-key')):
            result = details.get_game_details(620, '123')
            self.assertEqual(result, {'store': None, 'achievements': {'state': 'unavailable'}})
        with patch('steam_details._fetch_json', side_effect=self.upstream):
            self.assertEqual(details.get_game_details(620, '123')['achievements']['state'], 'ready')


if __name__ == '__main__':
    unittest.main()
