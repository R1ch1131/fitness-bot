import copy
import unittest
import types
from datetime import datetime
from unittest.mock import Mock, patch
import notification_history as history
import health_weights
import sleep_data
from notification_settings import TZ
from test_push import isolated_function


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.doc={'items':[]}
        read=patch.object(history,'_read',side_effect=lambda *a:copy.deepcopy(self.doc))
        write=patch.object(history,'_write',side_effect=lambda name,doc:self.doc.update(copy.deepcopy(doc)))
        read.start();write.start();self.addCleanup(read.stop);self.addCleanup(write.stop)

    def test_last_three_are_persisted_newest_first_without_subscription_keys_or_prompt(self):
        for i in range(5):
            history.record_sent(str(i),'body','/?tab=weekly','test',datetime(2026,11,6,10,i,tzinfo=TZ))
        self.assertEqual([n['title'] for n in history.latest()],['4','3','2'])
        self.assertEqual(set(history.latest()[0]),{'id','title','body','url','sent_at'})
        self.assertTrue(history.latest()[0]['sent_at'].endswith('+06:00'))
        for i in range(60): history.record_sent(str(i),'x','https://untrusted.test')
        self.assertEqual(len(self.doc['items']),50)
        self.assertEqual(history.latest()[0]['url'],'/')

    def test_empty_history_does_not_invent_old_notifications(self):
        self.assertEqual(history.latest(),[])

    def test_widget_auth_happens_before_loading_history_or_weight(self):
        class HttpError(Exception):
            def __init__(self,status_code,detail):self.status_code=status_code
        fn=isolated_function('api.py','overview_widget',{'Request':object,'HTTPException':HttpError,'JSONResponse':lambda data,**kw:data})
        with patch.object(sleep_data,'authorize',side_effect=PermissionError('wrong')),patch.object(health_weights,'widget_snapshot') as weights,patch.object(history,'latest') as recent:
            with self.assertRaises(HttpError) as caught:fn(types.SimpleNamespace(headers={}))
            self.assertEqual(caught.exception.status_code,401);weights.assert_not_called();recent.assert_not_called()
        with patch.object(sleep_data,'authorize'),patch.object(health_weights,'widget_snapshot',return_value={'current_weight':95}):
            data=fn(types.SimpleNamespace(headers={'authorization':'Bearer test'}))
            self.assertEqual(data['current_weight'],95);self.assertEqual(data['notifications'],[])
