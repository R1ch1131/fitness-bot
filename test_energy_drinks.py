import tempfile
import os
import io
import json
import urllib.error
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
  self.patchers=[patch.object(energy,'store',self.store),patch.object(energy,'is_cloud_configured',return_value=False),patch.object(energy,'search_upc',return_value=[])]
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

class SearchProviderFallbackTests(unittest.TestCase):
 def setUp(self):
  self.upc_patch=patch.object(energy,'search_upc',return_value=[])
  self.upc_patch.start();self.addCleanup(self.upc_patch.stop)
 def test_new_search_api_reads_hits_and_brands(self):
  with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0),patch.object(energy,'_get',return_value={'hits':[{'code':'1','product_name':'Monster','brands':['Monster','Juiced'],'image_front_url':'https://images.openfoodfacts.org/images/a.jpg'}]}) as get:
   result=energy.search_products('Monster')
   self.assertEqual(result['results'][0]['brand'],'Monster, Juiced')
   self.assertIn('search.openfoodfacts.org/search?',get.call_args.args[0])
 def test_old_endpoint_is_fallback_only(self):
  with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0),patch.object(energy,'_get',side_effect=[HTTPException(502,'Down'),{'products':[{'code':'1','product_name':'Drink','image_front_url':'https://images.openfoodfacts.org/images/a.jpg'}]}]) as get:
   self.assertEqual(len(energy.search_products('Drink')['results']),1)
   self.assertEqual(get.call_count,2)
   self.assertIn('cgi/search.pl',get.call_args.args[0])


class GeneralCatalogTests(unittest.TestCase):
 def test_retail_results_precede_off_and_are_cached(self):
  retail=[{'id':'upc:1','title':'Drink','image':'https://i5.walmartimages.com/a.jpg','source':'UPCitemdb'}]
  with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0),patch.object(energy,'search_upc',return_value=retail) as upc,patch.object(energy,'_upc_get') as off:
   self.assertEqual(energy.search_products('Drink')['results'],retail)
   self.assertEqual(energy.search_products('Drink')['results'],retail)
   upc.assert_called_once();off.assert_not_called()
 def test_upc_only_returns_safe_image_hosts_and_deduplicates(self):
  data={'code':'OK','items':[{'ean':'123','title':'Drink','images':['https://i5.walmartimages.com/a.jpg','https://i5.walmartimages.com/a.jpg']},{'title':'Wrong','images':['https://i5.walmartimages.com.evil.test/a.jpg']}]}
  with patch.object(energy,'_last_upc_search',0),patch.object(energy,'_upc_get',return_value=data):
   result=energy.search_upc('Drink')
   self.assertEqual(len(result),1);self.assertEqual(result[0]['source'],'UPCitemdb')
 def test_quota_and_unavailable_retail_service_allow_fallback(self):
  for response in [{'code':'TOO_MANY_REQUESTS'},{'code':'OK','items':[]}]:
   with patch.object(energy,'_last_upc_search',0),patch.object(energy,'_upc_get',return_value=response):self.assertEqual(energy.search_upc('Drink'),[])
  with patch.object(energy,'_last_upc_search',0),patch.object(energy,'_upc_get',side_effect=HTTPException(502,'Down')):self.assertEqual(energy.search_upc('Drink'),[])
 def test_retail_image_and_source_survive_validation(self):
  value=energy.DrinkInput(title='Drink',rating=8.5,image='https://i5.walmartimages.com/a.jpg',image_source='UPCitemdb')
  self.assertEqual(value.image_source,'UPCitemdb')
  with self.assertRaises(ValueError):energy.DrinkInput(title='Drink',image='https://i5.walmartimages.com.evil.test/a.jpg')


class SerperTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  for p in [patch.dict(os.environ, {'SERPER_API_KEY':'test-key'}), patch.object(energy,'is_cloud_configured',return_value=False), patch.object(energy,'SERPER_CACHE_FILE',Path(self.tmp.name)/'search.json'),patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0)]:
   p.start();self.addCleanup(p.stop)
  self.addCleanup(self.tmp.cleanup)
 def test_serper_search_saved_cache_survives_process_memory_reset(self):
  payload={'images':[{'title':'Monster can','imageUrl':'https://cdn.monsterenergy.com/can.png','link':'https://www.monsterenergy.com/product','source':'Monster'},{'title':'duplicate','imageUrl':'https://cdn.monsterenergy.com/can.png'},{'title':'private','imageUrl':'https://127.0.0.1/can.png'}]}
  with patch.object(energy,'_serper_request',return_value=payload) as provider,patch.object(energy,'search_upc') as upc:
   result=energy.search_products('Monster Mango')
   self.assertEqual(len(result['results']),1)
   self.assertTrue(result['cache_saved'])
   with patch.object(energy,'_search_cache',{}),patch.object(energy,'_last_search',0):
    self.assertTrue(energy.search_products('  monster  mango ')['cached'])
   provider.assert_called_once();upc.assert_not_called()
 def test_view_save_and_edit_never_call_serper(self):
  store=energy.DrinkStore(Path(self.tmp.name)/'drinks.json')
  app=FastAPI();app.include_router(energy.router)
  with patch.object(energy,'store',store),patch.object(energy,'_serper_request') as provider:
   client=TestClient(app)
   data={'title':'My drink','rating':8.5,'image_source':'Serper','image':'https://cdn.example.com/can.png','image_page':'https://example.com/drink'}
   result=client.post('/api/energy-drinks',json=data)
   self.assertEqual(result.status_code,200)
   item=result.json()['items'][0]
   self.assertEqual(item['image'],data['image'])
   self.assertEqual(item['image_page'],data['image_page'])
   self.assertEqual(client.get('/api/energy-drinks').json()['items'][0]['rating'],8.5)
   self.assertEqual(client.put('/api/energy-drinks/'+item['id'],json={**data,'rating':9}).status_code,200)
   provider.assert_not_called()
 def test_private_and_unsafe_web_images_blocked(self):
  for value in ['http://example.com/a.png','https://localhost/a.png','https://192.168.1.1/a.png','https://user:password@example.com/a.png','https://example.com:8443/a.png','data:text/html,no']:
   with self.assertRaises(ValueError):energy.DrinkInput(title='Drink',image=value,image_source='Serper')
 def test_cache_failure_does_not_spend_search(self):
  with patch.object(energy,'_read_image_cache',side_effect=HTTPException(503,'down')),patch.object(energy,'_serper_request') as provider:
   with self.assertRaises(HTTPException):energy.search_products('Monster')
   provider.assert_not_called()
 def test_provider_failure_does_not_silently_return_off(self):
  with patch.object(energy,'_serper_request',side_effect=HTTPException(503,'quota')),patch.object(energy,'_get') as off:
   with self.assertRaises(HTTPException):energy.search_products('Monster')
   off.assert_not_called()
 def test_request_sends_key_only_in_header_and_makes_one_call(self):
  with patch.object(energy.urllib.request,'urlopen',return_value=io.BytesIO(b'{"images":[]}')) as send:
   self.assertEqual(energy._serper_request('Monster','secret-key'),{'images':[]})
   request=send.call_args.args[0]
   self.assertEqual(request.full_url,'https://google.serper.dev/images')
   self.assertEqual(request.get_header('X-api-key'),'secret-key')
   self.assertNotIn('secret-key',request.data.decode())
   self.assertEqual(json.loads(request.data)['num'],10)
   send.assert_called_once()
 def test_upstream_errors_do_not_retry_or_expose_credentials(self):
  for code in (401,429):
   with patch.object(energy.urllib.request,'urlopen',side_effect=urllib.error.HTTPError('https://google.serper.dev/images',code,'secret-key',{},None)) as send:
    with self.assertRaises(HTTPException) as caught:energy._serper_request('Monster','secret-key')
    self.assertNotIn('secret-key',caught.exception.detail)
    send.assert_called_once()
