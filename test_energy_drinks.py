import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import energy_drinks as energy

class EnergyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=energy.DrinkStore(Path(self.tmp.name)/'energy.json')
  self.patchers=[patch.object(energy,'store',self.store),patch.object(energy,'is_cloud_configured',return_value=False)]
  for p in self.patchers:p.start()
  app=FastAPI();app.include_router(energy.router);self.client=TestClient(app)
 def tearDown(self):
  for p in self.patchers:p.stop()
  self.tmp.cleanup()
 def test_crud_decimal_zero_and_reload(self):
  r=self.client.post('/api/energy-drinks',json={'title':'  Monster Mango  ','rating':8.5,'notes':'Вкус манго'})
  self.assertEqual(r.status_code,200)
  item=r.json()['items'][0];self.assertEqual(item['title'],'Monster Mango')
  self.assertEqual(energy.DrinkStore(self.store.path).read()[0]['rating'],8.5)
  r=self.client.put('/api/energy-drinks/'+item['id'],json={'title':item['title'],'rating':0,'notes':'Changed'})
  self.assertEqual(r.json()['items'][0]['rating'],0)
  self.assertEqual(self.client.delete('/api/energy-drinks/'+item['id']).json()['items'],[])
  self.assertEqual(self.store.read(),[])
 def test_invalid_input_and_untrusted_image_rejected(self):
  for value in [{'title':' '},{'title':'Drink','rating':11},{'title':'Drink','rating':-1},{'title':'Drink','image':'https://images.openfoodfacts.org.evil.test/a.jpg'}]:
   self.assertEqual(self.client.post('/api/energy-drinks',json=value).status_code,422)
  self.assertEqual(self.store.read(),[])
 def test_cloud_read_failure_never_overwrites(self):
  from cloud_storage import CloudStorageError
  with patch.object(energy,'is_cloud_configured',return_value=True),patch.object(energy,'get_cloud_data',side_effect=CloudStorageError('Down')),patch.object(energy,'set_cloud_data') as write:
   self.assertEqual(self.client.post('/api/energy-drinks',json={'title':'Drink'}).status_code,503)
   write.assert_not_called()
 def test_cloud_write_failure_is_not_success(self):
  with patch.object(energy,'is_cloud_configured',return_value=True),patch.object(energy,'get_cloud_data',return_value=[]),patch.object(energy,'set_cloud_data',return_value=False):
   self.assertEqual(self.client.post('/api/energy-drinks',json={'title':'Drink'}).status_code,503)
 def test_search_filters_image_hosts_and_caches(self):
  with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0),patch.object(energy,'_get',return_value={'products':[{'code':'1','product_name':'Drink','image_front_url':'https://images.openfoodfacts.org/images/a.jpg'},{'code':'2','product_name':'Wrong','image_front_url':'https://evil.test/a.jpg'}]}) as get:
   result=energy.search_products('Monster')
   self.assertEqual(len(result['results']),1)
   self.assertEqual(energy.search_products('Monster'),result);get.assert_called_once()
   with self.assertRaises(HTTPException) as caught:energy.search_products('Other')
   self.assertEqual(caught.exception.status_code,429)
 def test_search_failure_is_actionable(self):
  with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0),patch.object(energy,'_get',side_effect=HTTPException(502,'Down')):
   with self.assertRaises(HTTPException) as caught:energy.search_products('Monster')
   self.assertIn('свою картинку',caught.exception.detail)
