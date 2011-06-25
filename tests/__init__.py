import functools
import unittest2

from sentry import app
from sentry.db import get_backend

def with_settings(**settings):
    def wrapped(func):
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            defaults = {}
            for k, v in settings.iteritems():
                defaults[k] = app.config.get(k)
                app.config[k] = v
            try:
                return func(*args, **kwargs)
            finally:
                for k, v in defaults.iteritems():
                    app.config[k] = v
        return _wrapped
    return wrapped

class BaseTest(unittest2.TestCase):
    def setUp(self):
        # XXX: might be a better way to do do this
        app.config['DATASTORE'] = {
            'ENGINE': 'sentry.db.backends.redis.RedisBackend',
            'OPTIONS': {
                'db': 9
            }
        }
        app.config['CLIENT'] = 'sentry.client.base.SentryClient'
        app.db = get_backend(app)
        
        # Flush the Redis instance
        app.db.conn.flushdb()
        
        self.client = app.test_client()
