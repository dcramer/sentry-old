from .. import BaseTest


from sentry.db.backends.redis import RedisBackend

class MockModel(object):
    __name__ = 'test'

class RedisBackendTest(BaseTest):
    def setUp(self):
        self.backend = RedisBackend(db=9)
        self.schema = MockModel()
        self.redis = self.backend.conn
        
    def test_add(self):
        pk1 = self.backend.add(self.schema, **{'foo': 'bar'})
        self.assertTrue(pk1)

        key = self.backend._get_data_key(self.schema, pk1)
        self.assertEquals(len(self.redis.hgetall(key)), 1)
        self.assertEquals(self.redis.hget(key, 'foo'), 'bar')
        
        pk2 = self.backend.add(self.schema)
        self.assertTrue(pk2)
        self.assertNotEquals(pk1, pk2)

        key = self.backend._get_data_key(self.schema, pk2)
        self.assertFalse(self.redis.hgetall(key))

    def test_delete(self):
        pk = 'foo'
        key = self.backend._get_data_key(self.schema, pk)
        metakey = self.backend._get_metadata_key(self.schema, pk)

        self.redis.hset(key, pk, {'foo': 'bar'})
        self.redis.hset(metakey, pk, {'foo': 'bar'})
        
        self.backend.delete(self.schema, pk)
        
        self.assertFalse(self.redis.hgetall(key))
        self.assertFalse(self.redis.hgetall(metakey))
