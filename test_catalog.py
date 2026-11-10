import unittest
from unittest.mock import patch
from fastapi import HTTPException
from catalog import search_catalog, catalog_details
from media_library import MediaInput, MediaLibrary
from media_covers import normalize_cover
from pathlib import Path
from tempfile import TemporaryDirectory

class CatalogTests(unittest.TestCase):
    def test_book_edition_details_not_median_page_guess(self):
        with patch('catalog._get', return_value={'docs':[{'key':'/works/OL1W','title':'Book','author_name':['Author'],'first_publish_year':1950,'editions':{'docs':[{'key':'/books/OL2M','title':'Edition'}]}}]}):
            result=search_catalog('book','Book')['results'][0]
        self.assertEqual(result['title'],'Edition')
        self.assertIsNone(result['pages'])
        with patch('catalog._get', return_value={'number_of_pages':340,'publishers':['Press'],'publish_date':'2020','covers':[123]}):
            detail=catalog_details('book',result['external_id'])
        self.assertEqual(detail['pages'],340)
        self.assertEqual(detail['image'],'https://covers.openlibrary.org/b/id/123-L.jpg')

    def test_anime_unknown_episodes_and_score_remain_unknown(self):
        with patch.dict('os.environ', {'TMDB_READ_TOKEN':'secret'}), patch('catalog._get', return_value={'results':[{'id':1,'name':'Test','media_type':'tv','genre_ids':[16]}]}):
            result=search_catalog('anime','Test')['results'][0]
        self.assertIsNone(result['episodes'])
        self.assertIsNone(result['score'])

    def test_tmdb_without_key_is_actionable(self):
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':''}),patch('catalog._get') as get:
            with self.assertRaises(HTTPException) as error: search_catalog('movie','Test')
        self.assertEqual(error.exception.status_code,503)
        self.assertIn('TMDB_READ_TOKEN',error.exception.detail)
        get.assert_not_called()

    def test_tmdb_token_only_in_server_header_and_unknown_rating(self):
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':'secret'}),patch('catalog._get',return_value={'results':[{'id':3,'name':'Series','vote_average':0,'vote_count':0,'poster_path':'/a.jpg'}]}) as get:
            result=search_catalog('series','Series')['results'][0]
        self.assertNotIn('secret',get.call_args.args[0])
        self.assertEqual(get.call_args.args[1],{'Authorization':'Bearer secret'})
        self.assertIsNone(result['score'])

    def test_catalog_covers_are_allowlisted(self):
        for host in ['covers.openlibrary.org','cdn.myanimelist.net','image.tmdb.org']:
            self.assertEqual(normalize_cover('https://'+host+'/image.jpg'),'https://'+host+'/image.jpg')
        with self.assertRaises(ValueError):normalize_cover('https://image.tmdb.org.evil.test/image.jpg')

    def test_media_metadata_survives_old_client_update_and_episode_completion(self):
        with TemporaryDirectory() as directory,patch('media_library.get_cloud_data',return_value=None),patch('media_library.set_cloud_data'):
            library=MediaLibrary(Path(directory)/'media.json')
            first=library.save(MediaInput(title='Test',kind='anime',total=12,progress=11,rating=9,notes='Personal',catalog={'source':'Shikimori','external_id':'1','title':'Test','score':8},cover_image='https://cdn.myanimelist.net/a.jpg'))['items'][0]
            last=library.save(MediaInput(title='Test',kind='anime',total=12,progress=12,rating=9,notes='Personal'),first['id'])['items'][0]
            self.assertEqual(last['catalog']['score'],8)
            self.assertEqual(last['rating'],9)
            self.assertEqual(last['notes'],'Personal')
            self.assertEqual(last['status'],'finished')
            self.assertEqual(last['cover_image'],first['cover_image'])

    def test_book_catalog_survives_progress_update(self):
        import copy
        from unittest.mock import Mock
        from books_manager import BooksManager
        manager = BooksManager.__new__(BooksManager)
        rows=[]
        manager.get_books=lambda:copy.deepcopy(rows)
        manager._save=lambda items:rows.__setitem__(slice(None),copy.deepcopy(items))
        manager._mark_reading_habit_for_today=Mock()
        book=manager.add_book('Title','Author',total_pages=400,catalog={'source':'Open Library','external_id':'/books/OL1M','title':'Title'},cover_image='https://covers.openlibrary.org/b/id/1-L.jpg')
        updated=manager.update_book(book['id'],current_page=20)
        self.assertEqual(updated['catalog'],book['catalog'])
        self.assertEqual(updated['cover_image'],book['cover_image'])
        self.assertEqual(updated['current_page'],20)
        manager.update_book(book['id'],cover_image='')
        self.assertIsNone(rows[0]['cover_image'])

    def test_details_cannot_fetch_arbitrary_paths(self):
        with patch('catalog._get') as get:
            self.assertEqual(catalog_details('book','//evil.test/a'),{})
            self.assertEqual(catalog_details('series','../configuration'),{})
            get.assert_not_called()

class AnimePosterTests(unittest.TestCase):
    anime = {'id':1535,'kind':'tv','name':'Death Note','russian':'Тетрадь смерти','aired_on':'2006-10-04','image':{'original':'/assets/globals/missing_original.jpg'}}
    def candidate(self, **changes):
        return {'id':13916,'name':'Тетрадь смерти','original_name':'Death Note','first_air_date':'2006-10-04','genre_ids':[16],'poster_path':'/poster.jpg',**changes}
    def run_search(self, candidates):
        from catalog import anime_posters
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':'secret'}),patch('catalog._get',return_value={'results':candidates}):
            return anime_posters(self.anime)
    def test_unique_title_and_year_match_is_automatic(self):
        result=self.run_search([self.candidate()])
        self.assertEqual(result['poster_state'],'matched')
        self.assertEqual(result['image'],'https://image.tmdb.org/t/p/w500/poster.jpg')
        self.assertEqual(result['poster_source'],'TMDB')
    def test_same_title_different_year_requires_choice(self):
        result=self.run_search([self.candidate(first_air_date='2017-01-01')])
        self.assertEqual(result['poster_state'],'choose')
        self.assertNotIn('image',result)
    def test_two_exact_matches_require_choice(self):
        result=self.run_search([self.candidate(),self.candidate(id=2)])
        self.assertEqual(result['poster_state'],'choose')
        self.assertEqual(len(result['poster_options']),2)
    def test_live_action_is_not_offered(self):
        result=self.run_search([self.candidate(genre_ids=[18])])
        self.assertEqual(result['poster_state'],'not_found')
    def test_unknown_year_never_automatches(self):
        from catalog import anime_posters
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':'secret'}),patch('catalog._get',return_value={'results':[self.candidate()]}):
            result=anime_posters({**self.anime,'aired_on':None})
        self.assertEqual(result['poster_state'],'choose')
    def test_optional_tmdb_failure_does_not_lose_anime_details(self):
        def get(url, headers=None):
            if 'shikimori' in url:return {**self.anime,'description':'Описание','episodes':37}
            raise HTTPException(502,'Unavailable')
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':'secret'}),patch('catalog._get',side_effect=get):
            result=catalog_details('anime','1535')
        self.assertEqual(result['description'],'Описание')
        self.assertEqual(result['episodes'],37)
        self.assertEqual(result['poster_state'],'unavailable')
    def test_existing_shikimori_art_does_not_query_tmdb(self):
        with patch('catalog._get',return_value={**self.anime,'image':{'original':'/system/animes/original/1535.jpg'}}) as get:
            result=catalog_details('anime','1535')
        self.assertEqual(get.call_count,1)
        self.assertNotIn('poster_state',result)
    def test_missing_key_does_not_query_tmdb(self):
        from catalog import anime_posters
        with patch.dict('os.environ',{'TMDB_READ_TOKEN':''}),patch('catalog._get') as get:
            result=anime_posters(self.anime)
        get.assert_not_called()
        self.assertEqual(result['poster_state'],'no_key')

if __name__=='__main__':unittest.main()

class AnimeTMDBTests(unittest.TestCase):
    @patch.dict('os.environ', {'TMDB_READ_TOKEN': 'secret'})
    def test_search_filters_adaptations_and_namespaces_ids(self):
        payload = {'results': [{'id': 7, 'name': 'Anime', 'media_type': 'tv', 'genre_ids': [16], 'poster_path': '/a.jpg'}, {'id': 7, 'title': 'Film', 'media_type': 'movie', 'genre_ids': [16]}, {'id': 8, 'name': 'Live action', 'media_type': 'tv', 'genre_ids': [18]}, {'id': 9, 'name': 'Person', 'media_type': 'person'}]}
        with patch('catalog._get', return_value=payload) as get:
            items = search_catalog('anime', 'Anime')['results']
        self.assertEqual([i['external_id'] for i in items], ['tmdb:tv:7', 'tmdb:movie:7'])
        self.assertTrue(all(i['source'] == 'TMDB' for i in items))
        self.assertIn('/search/multi?', get.call_args.args[0])
        self.assertNotIn('secret', get.call_args.args[0])

    @patch.dict('os.environ', {'TMDB_READ_TOKEN': 'secret'})
    def test_season_counts_and_persistence(self):
        with patch('catalog._get', return_value={'name': 'Anime', 'number_of_episodes': 36, 'poster_path': '/show.jpg', 'seasons': [{'season_number': 1, 'name': 'Season 1', 'episode_count': 12}, {'season_number': 2, 'name': 'Season 2', 'episode_count': 24}]}) as get:
            options = catalog_details('anime', 'tmdb:tv:7')['season_options']
        self.assertEqual([o['episodes'] for o in options], [12, 24])
        self.assertEqual(options[1]['external_id'], 'tmdb:tv:7:season:2')
        with patch('catalog._get', return_value={'episodes': [{}, {}], 'poster_path': '/season.jpg'}) as get:
            detail = catalog_details('anime', options[1]['external_id'])
        self.assertEqual(detail['episodes'], 2)
        self.assertIn('/tv/7/season/2?', get.call_args.args[0])
        entry = MediaInput(title='Anime', kind='anime', total=24, progress=11, notes='Keep', rating=9, catalog=options[1])
        self.assertEqual(entry.catalog.external_id, 'tmdb:tv:7:season:2')
        self.assertEqual(entry.progress, 11)

    def test_invalid_tmdb_id_never_requested(self):
        with patch('catalog._get') as get:
            self.assertEqual(catalog_details('anime', 'tmdb:tv:../secret'), {})
            self.assertEqual(catalog_details('anime', 'tmdb:movie:7:season:2'), {})
        get.assert_not_called()
