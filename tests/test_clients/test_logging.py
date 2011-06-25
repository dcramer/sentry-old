from .. import BaseTest

import logging

from sentry.client import get_client
from sentry.models import Event

class LoggingTest(BaseTest):
    def test_simple(self):
        client = get_client('sentry.client.logging.LoggingSentryClient')
        
        _foo = {'': None}
        
        class handler(logging.Handler):
            def emit(self, record):
                _foo[''] = record

        logger = client.logger
        logger.addHandler(handler())
        
        event_id = client.capture('Message', message='hello world')
        
        self.assertRaises(Event.DoesNotExist, Event.objects.get, event_id)
        
        self.assertEquals(_foo[''].getMessage(), 'hello world')
        self.assertEquals(_foo[''].levelno, client.default_level)
