from .. import BaseTest

from logbook import Logger
from sentry.contrib.logbook import SentryHandler
from sentry.models import Event

class LogbookTest(BaseTest):
    def test_simple(self):
        logger = Logger('sentry.tests.test_contrib.test_logbook')
        handler = SentryHandler('INFO')
        with handler.applicationbound():
            logger.warn('foo')
        
        event = Event.objects.all()[0]

        self.assertEquals(event.type, 'sentry.events.Message')
        self.assertEquals(event.time_spent, 0)
        self.assertTrue('sentry.interfaces.Message' in event.data)
        event_data = event.data['sentry.interfaces.Message']
        self.assertTrue('message' in event_data)
        self.assertEquals(event_data['message'], 'foo')
        self.assertTrue('params' in event_data)
        self.assertEquals(event_data['params'], [])
        
        tags = dict(event.tags)
        self.assertTrue('level' in tags)
        self.assertEquals(tags['level'], 'warning')

    def test_exception(self):
        logger = Logger('sentry.tests.test_contrib.test_logbook')
        handler = SentryHandler('INFO')
        with handler.applicationbound():
            try:
                raise ValueError('foo')
            except:
                logger.exception('foo bar')
        
        event = Event.objects.all()[0]

        self.assertEquals(event.type, 'sentry.events.Exception')
        self.assertEquals(event.time_spent, 0)
        self.assertTrue('sentry.interfaces.Exception' in event.data)
        event_data = event.data['sentry.interfaces.Exception']
        self.assertTrue('type' in event_data)
        self.assertEquals(event_data['type'], 'ValueError')
        self.assertTrue('value' in event_data)
        self.assertEquals(event_data['value'], 'foo')
        
        tags = dict(event.tags)
        self.assertTrue('level' in tags)
        self.assertEquals(tags['level'], 'error')
