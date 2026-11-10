import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from fastapi import HTTPException
from book_catalog import find_books,google_details,google_volume,romanize

class BookCatalogTests(unittest.TestCase):
 def test_russian_title_can_find_transliterated_edition_and_edition_cover_wins(self):
  calls=[]
  def get(url):
   q=parse_qs(urlsplit(url).query);calls.append(q)
   return {'docs':[{'key':'/works/OL1W','title':'Marsianin','cover_i':111,'author_name':['Vejer E.'],'editions':{'docs':[{'key':'/books/OL2M','title':'Marsianin','cover_i':222}]}}]} if q.get('title')==['marsianin'] else {'docs':[]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':''}):items=find_books('Марсианин','Энди Вейер',get)
  self.assertEqual(romanize('Марсианин'),'marsianin')
  self.assertEqual(items[0]['external_id'],'/books/OL2M')
  self.assertIn('/222-L.jpg?default=false',items[0]['image'])
  self.assertEqual(len(calls),2)
 def test_google_metadata_and_image_use_https_without_credentials(self):
  item=google_volume({'id':'abc-1','volumeInfo':{'title':'Book','authors':['Author'],'pageCount':240,'description':'<b>Hello</b> world','imageLinks':{'thumbnail':'http://books.google.com/books/content?id=abc-1&key=secret'},'industryIdentifiers':[{'type':'ISBN_13','identifier':'9785000571439'}]}})
  self.assertEqual(item['source'],'Google Books')
  self.assertEqual(item['external_id'],'google:abc-1')
  self.assertEqual(item['pages'],240)
  self.assertNotIn('secret',str(item))
  self.assertTrue(item['image'].startswith('https://books.google.com/'))
  self.assertNotIn('<b>',item['description'])
 def test_no_google_requests_without_own_key(self):
  calls=[]
  def get(url):calls.append(url);return {'docs':[]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':''}):find_books('Book','',get)
  self.assertTrue(all('openlibrary.org' in url for url in calls))
 def test_google_failure_keeps_open_library_available(self):
  def get(url):
   if 'googleapis.com' in url:raise HTTPException(502,'Quota')
   return {'docs':[{'key':'/works/OL1W','title':'Book','cover_i':123}]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':'secret'}):items=find_books('Book','',get)
  self.assertEqual(items[0]['source'],'Open Library')
 def test_google_details_does_not_fetch_untrusted_identifier(self):
  with self.assertRaises(HTTPException):google_details('google:../secrets',lambda _:self.fail('unexpected request'))
 def test_author_fallback_is_a_manual_result_without_auto_assignment(self):
  def get(url):
   q=parse_qs(urlsplit(url).query)
   return {'docs':[{'key':'/works/OL1W','title':'The 12-week year','author_name':['Brian Moran'],'cover_i':123}]} if q.get('author')==['moran'] else {'docs':[]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':''}):items=find_books('12 недель в году','Брайан Моран и Майкл Леннингтон',get)
  self.assertEqual(items[0]['title'],'The 12-week year')

class GoogleRelevanceTests(unittest.TestCase):
 def test_original_editions_precede_summaries_and_query_is_title_scoped(self):
  seen=[]
  def get(url):
   query=parse_qs(urlsplit(url).query);seen.append(query)
   return {'items':[
    {'id':'summary','volumeInfo':{'title':'12 недель в году. Кратко','authors':['Культур-Мультур']}},
    {'id':'original','volumeInfo':{'title':'12 недель в году','authors':['Брайан Моран']}},
    {'id':'frankl','volumeInfo':{'title':'Краткая история времени','authors':['Стивен Хокинг']}}
   ]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':'secret'}):items=find_books('12 недель в году','Брайан Моран',get)
  self.assertEqual(items[0]['external_id'],'google:original')
  self.assertEqual(seen[0]['q'],['intitle:"12 недель в году"'])
  self.assertEqual(seen[0]['maxResults'],['20'])
  self.assertEqual(len(seen),1)
 def test_isbn_keeps_exact_query(self):
  seen=[]
  def get(url):
   query=parse_qs(urlsplit(url).query);seen.append(query)
   return {'items':[{'id':'edition','volumeInfo':{'title':'Book'}}]}
  with patch.dict('os.environ',{'GOOGLE_BOOKS_API_KEY':'secret'}):find_books('978-5-17-112622-3','Other author',get)
  self.assertEqual(seen[0]['q'],['isbn:9785171126223'])

if __name__=='__main__':unittest.main()

class DescriptionFallbackTests(unittest.TestCase):
 def test_edition_follows_linked_work(self):
  from book_catalog import open_library_description
  def get(url):
   return {'works':[{'key':'/works/OL1W'}]} if '/books/' in url else {'description':{'value':'Аннотация произведения'}}
  self.assertEqual(open_library_description('/books/OL2M',get),'Аннотация произведения')
 def test_google_missing_description_uses_matching_work_and_attributes_source(self):
  from book_catalog import supplement_description
  def get(url):
   if 'search.json' in url:return {'docs':[{'key':'/works/OL1W','title':'Book','author_name':['Some Author']}]}
   return {'description':'Work description'}
  result=supplement_description({'title':'Book','author':'Some Author','source':'Google Books','external_id':'google:abc','pages':237},get)
  self.assertEqual(result['description_source'],'Open Library')
  self.assertEqual(result['pages'],237)
  self.assertEqual(result['external_id'],'google:abc')
 def test_wrong_author_or_ambiguous_work_never_enriched(self):
  from book_catalog import supplement_description
  for rows in [[{'key':'/works/OL1W','title':'Book','author_name':['Other Person']}],[{'key':key,'title':'Book','author_name':['Some Author']} for key in ['/works/OL1W','/works/OL2W']]]:
   calls=[]
   def get(url):calls.append(url);return {'docs':rows}
   result=supplement_description({'title':'Book','author':'Some Author'},get)
   self.assertNotIn('description',result)
   self.assertEqual(len(calls),1)
 def test_existing_description_and_invalid_link_skip_external_requests(self):
  from book_catalog import supplement_description,open_library_description
  def get(url):self.fail('Unexpected external request')
  self.assertEqual(supplement_description({'description':'Existing'},get),{'description':'Existing'})
  self.assertEqual(open_library_description('//evil.test',get),'')
 def test_optional_provider_failure_preserves_selected_book(self):
  from book_catalog import supplement_description
  def get(url):raise HTTPException(502,'Down')
  original={'title':'Book','author':'Author','pages':237}
  self.assertEqual(supplement_description(original,get),original)
