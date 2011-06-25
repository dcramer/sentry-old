from .. import BaseTest, with_settings

import base64
import simplejson
from sentry.models import Event

class StoreTest(BaseTest):
    @with_settings(PUBLIC_WRITES=True)
    def test_simple(self):
        response = self.client.post('/api/store/', data=base64.b64encode(simplejson.dumps({
            "event_type": "sentry.events.Exception",
            "tags": [ ["level", "error"], ["server", "sentry.local"] ],
            "date": "2010-06-18T22:31:45",
            "time_spent": 0.0,
            "event_id": "452dfa92380f438f98159bb75b9469e5",
            "data": {
                "culprit": "path.to.function",
                "version": ["module", "version string"],
                "modules": {
                    "module": "version string"
                },
                "extra": {
                    "key": "value",
                },
                "sentry.interfaces.Http": {
                    "url": "http://example.com/foo/bar",
                    "method": "POST",
                    "querystring": "baz=bar&foo=baz",
                    "data": {
                        "key": "value"
                    }
                },
                "sentry.interfaces.Exception": {
                    "type": "ValueError",
                    "value": "An example exception",
                    "frames": [
                        {
                            "filename": "/path/to/filename.py",
                            "module": "path.to.module",
                            "function": "function_name",
                            "vars": {
                                "key": "value"
                            }
                        }
                    ]
                }
            }
        }).encode('zlib')))
        
        self.assertEquals(response.status_code, 200)

        event_id = response.data
        
        event = Event.objects.get(event_id)

        self.assertTrue('sentry.interfaces.Http' in event.data)
        
        result = event.data['sentry.interfaces.Http']

        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/bar')
        self.assertTrue('method' in result, result)
        self.assertEquals(result['method'], 'POST')
        self.assertTrue('data' in result, result)
        self.assertTrue('key' in result['data'])
        self.assertEquals(result['data']['key'], 'value')
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'baz=bar&foo=baz')