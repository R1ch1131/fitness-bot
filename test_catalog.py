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
        with patch('catalog._get', return_value=[{'id':1,'name':'Test','episodes':None,'score':None}]):
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

if __name__=='__main__':unittest.main()
