from .. import BaseTest

from sentry.db.backends.redis import RedisBackend

class MockModel(object):
    __name__ = 'test'

class RedisBackendTest(BaseTest):
    def setUp(self):
        self.backend = RedisBackend(db=9)
        self.schema = MockModel()

    def test_add(self):
        pk1 = self.backend.add(self.schema, **{'foo': 'bar'})
        self.assertTrue(pk1)
        
        pk2 = self.backend.add(self.schema)
        self.assertTrue(pk2)
        self.assertNotEquals(pk1, pk2)