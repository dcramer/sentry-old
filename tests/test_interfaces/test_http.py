from .. import BaseTest

from sentry import capture
from sentry.models import Event
from sentry.core.interfaces import Http, unserialize

class HttpIntegrationTest(BaseTest):
    def test_create(self):
        event_id = capture('Message', message='hello world', data={
            'sentry.core.interfaces.Http': {
                'url': 'http://example.com/foo/?bar=baz',
                'method': 'GET',
            }
        })

        event = Event.objects.get(event_id)

        self.assertTrue('sentry.core.interfaces.Http' in event.data)
        
        result = event.data['sentry.core.interfaces.Http']

        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/')
        self.assertTrue('method' in result, result)
        self.assertEquals(result['method'], 'GET')
        self.assertTrue('data' in result, result)
        self.assertEquals(result['data'], {})
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'bar=baz')
        
class HttpTest(BaseTest):
    def test_unserialize(self):
        http = unserialize(Http, {
            'url': 'http://example.com/foo/',
            'method': 'GET',
            'data': {},
            'querystring': 'bar=baz',
        })
        self.assertEquals(http.url, 'http://example.com/foo/')
        self.assertEquals(http.method, 'GET')
        self.assertEquals(http.data, {})
        self.assertEquals(http.querystring, 'bar=baz')

    def test_serialize(self):
        http = Http('http://example.com/foo/', 'GET', {}, 'bar=baz')
        result = http.serialize()
        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/')
        self.assertTrue('method' in result, result)
        self.assertEquals(result['method'], 'GET')
        self.assertTrue('data' in result, result)
        self.assertEquals(result['data'], {})
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'bar=baz')

    def test_serialize_and_unserialize(self):
        http = Http('http://example.com/foo/', 'GET', {}, 'bar=baz')
        result = unserialize(Http, http.serialize()).serialize()
        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/')
        self.assertTrue('method' in result, result)
        self.assertEquals(result['method'], 'GET')
        self.assertTrue('data' in result, result)
        self.assertEquals(result['data'], {})
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'bar=baz')

    def test_querystring_extraction(self):
        http = Http('http://example.com/foo/?bar=baz', 'GET')
        result = http.serialize()
        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/')
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'bar=baz')

    def test_querystring_prefix(self):
        http = Http('http://example.com/foo/', 'GET', {}, '?bar=baz')
        result = http.serialize()
        self.assertTrue('url' in result, result)
        self.assertEquals(result['url'], 'http://example.com/foo/')
        self.assertTrue('querystring' in result, result)
        self.assertEquals(result['querystring'], 'bar=baz')

    def test_lowercase_method(self):
        http = Http('http://example.com/foo/?bar=baz', 'get')
        result = http.serialize()
        self.assertTrue('method' in result, result)
        self.assertEquals(result['method'], 'GET')

    def test_invalid_method(self):
        self.assertRaises(AssertionError, Http, 'http://example.com/foo/?bar=baz', 'biz')
