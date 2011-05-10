import unittest2

from sentry import app
from sentry.db import get_backend

class BaseTest(unittest2.TestCase):
    def setUp(self):
        # XXX: might be a better way to do do this
        app.config['DATASTORE'] = {
            'ENGINE': 'sentry.db.backends.redis.RedisBackend',
            'OPTIONS': {
                'db': 9
            }
        }
        app.db = get_backend(app)
        
        # Flush the Redis instance
        app.db.conn.flushdb()