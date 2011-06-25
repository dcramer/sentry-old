from .. import BaseTest

from sentry.core.interfaces import Http

class HttpTest(BaseTest):
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
