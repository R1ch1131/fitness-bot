"""Persistence boundaries: failed cloud requests must never reset a collection."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from cloud_storage import CloudStorageError, get_cloud_data
from media_library import MediaInput, MediaLibrary, RestoreMediaInput, router


class MediaStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cloud=None
        self.fail_read=False
        self.fail_write=False
        self.writes=0
        def read(_key, **_options):
            if self.fail_read: raise CloudStorageError('network')
            return json.loads(json.dumps(self.cloud))
        def write(_key, value):
            self.writes+=1
            if self.fail_write:return False
            self.cloud=json.loads(json.dumps(value))
            return True
        for name, options in [('is_cloud_configured',{'return_value':True}),('get_cloud_data',{'side_effect':read}),('set_cloud_data',{'side_effect':write})]:
            self.addCleanup(patch.stopall)
            patch('media_library.'+name,**options).start()
        self.path=Path(self.tmp.name)/'media.json'
        self.manager=MediaLibrary(self.path)
    def seed(self):
        return self.manager.save(MediaInput(title='Film',kind='movie',rating=5.5,notes='Personal'))['items'][0]
    def test_redeploy_with_empty_filesystem_recovers_ratings_and_notes(self):
        expected=self.seed()
        restored=MediaLibrary(Path(self.tmp.name)/'new-container'/'media.json').items()
        self.assertEqual(restored,[expected])
        self.assertEqual(restored[0]['rating'],5.5)
    def test_failed_cloud_save_preserves_disk_and_snapshot(self):
        old=self.seed();before=self.path.read_bytes();self.fail_write=True
        with self.assertRaises(HTTPException) as error:
            self.manager.save(MediaInput(title='Changed',kind='movie',rating=9),old['id'])
        self.assertEqual(error.exception.status_code,503)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.manager.items(),[old])
        self.assertEqual(self.cloud,[old])
    def test_read_failure_does_not_initialize_empty_or_migrate_local_data(self):
        old=self.seed();self.fail_read=True;before=self.path.read_bytes();writes=self.writes
        new=MediaLibrary(self.path)
        with self.assertRaises(HTTPException):new.items()
        self.assertFalse(new.loaded)
        self.assertEqual(self.writes,writes)
        self.assertEqual(self.path.read_bytes(),before)
        self.fail_read=False
        self.assertEqual(new.items(),[old])
    def test_confirmed_empty_cloud_does_not_resurrect_deleted_records(self):
        self.seed();self.cloud=[]
        self.assertEqual(MediaLibrary(self.path).items(),[])
    def test_confirmed_missing_cloud_key_migrates_existing_local_collection(self):
        old=self.seed();self.cloud=None
        self.assertEqual(MediaLibrary(self.path).items(),[old])
        self.assertEqual(self.cloud,[old])
    def test_local_disk_failure_after_confirmed_cloud_save_keeps_server_consistent(self):
        with patch.object(self.manager,'_write_local',side_effect=OSError('read only')):
            self.seed()
        self.assertEqual(self.manager.items(),self.cloud)
        self.assertEqual(MediaLibrary(self.path).items(),self.cloud)
    def test_restore_is_validated_and_preserves_steam_metadata(self):
        old=self.seed()
        value=RestoreMediaInput(items=[{**old,'kind':'game','steam_appid':620,'steam_playtime_minutes':301,'cover_image':'https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg'}])
        self.manager.restore(value)
        self.assertEqual(self.cloud[0]['steam_appid'],620)
        self.assertEqual(self.cloud[0]['rating'],5.5)
        self.fail_write=True
        with self.assertRaises(HTTPException): self.manager.restore(RestoreMediaInput(items=[]))
        self.assertEqual(len(self.manager.items()),1)
    def test_storage_endpoint_checks_cloud_and_returns_no_credentials(self):
        self.seed()
        with patch('media_library.library',self.manager):
            app=FastAPI();app.include_router(router);client=TestClient(app)
            self.assertEqual(client.get('/api/media/storage').json()['state'],'verified')
            response=client.post('/api/media/restore',json={'items':[{'title':'bad','kind':'movie'}]})
            self.assertEqual(response.status_code,422)
            self.fail_read=True
            self.assertEqual(client.get('/api/media/storage').status_code,503)
        self.assertEqual(len(self.cloud),1)
    def test_general_backup_contains_media_and_restore_can_clear_it(self):
        tree=ast.parse(Path('api.py').read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('get_backup','restore_backup')]
        for node in nodes:node.decorator_list=[]
        namespace={'datetime':__import__('datetime').datetime,'TZ_GMT6':__import__('datetime').timezone.utc,'books_mgr':Mock(),'habits_mgr':Mock(),'media_store':self.manager,'RestoreBackupPayload':SimpleNamespace,'RestoreMediaInput':RestoreMediaInput}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'api.py','exec'),namespace)
        old=self.seed()
        self.assertEqual(namespace['get_backup']()['media'],[old])
        namespace['restore_backup'](SimpleNamespace(media=[],books=None,habits=None))
        self.assertEqual(self.cloud,[])


class StrictCloudReadTests(unittest.TestCase):
    def test_provider_error_is_not_missing_key(self):
        response=Mock();response.read.return_value=b'{"error":"timeout"}'
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        with patch('cloud_storage.is_cloud_configured',return_value=True),patch('cloud_storage.UPSTASH_URL','https://example.test'),patch('urllib.request.urlopen',return_value=context):
            with self.assertRaises(CloudStorageError):get_cloud_data('athlete_media',strict=True)
            self.assertIsNone(get_cloud_data('athlete_books'))

if __name__=='__main__':unittest.main()
