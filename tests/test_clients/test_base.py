from .. import BaseTest

from sentry import app
from sentry.client import ClientProxy
from sentry.client.logging import LoggingSentryClient

class ClientTest(BaseTest):
    def test_client_proxy(self):
        proxy = ClientProxy(app)

        app.config['CLIENT'] = 'sentry.client.logging.LoggingSentryClient'

        self.assertTrue(isinstance(proxy._ClientProxy__get_client(), LoggingSentryClient))
        self.assertEquals(proxy._ClientProxy__get_client(), proxy._ClientProxy__get_client())
    
        app.config['CLIENT'] = 'sentry.client.base.SentryClient'
        
        self.assertFalse(isinstance(proxy._ClientProxy__get_client(), LoggingSentryClient))
        self.assertEquals(proxy._ClientProxy__get_client(), proxy._ClientProxy__get_client())
