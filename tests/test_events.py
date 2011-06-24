from . import BaseTest

import datetime
import sys

from sentry import app, capture
from sentry.models import Event, Tag, Group

class SentryTest(BaseTest):
    # Some quick ugly high level tests to get shit working fast
    def test_create(self):
        # redis is so blazing fast that we have to artificially inflate dates
        # or tests wont pass :)
        now = datetime.datetime.now()

        event, group = app.client.store(
            'sentry.events.Message',
            tags=(
                ('server', 'foo.bar'),
                ('culprit', 'foo.bar.zoo.baz'),
            ),
            date=now,
            time_spent=53,
            data={
                '__event__': {
                    'message': 'hello world'
                }
            },
            event_id='foobar',
        )
        group_id = group.pk

        self.assertTrue(group.pk)
        self.assertEquals(group.type, 'sentry.events.Message')
        self.assertEquals(group.time_spent, 53)
        self.assertEquals(group.count, 1)
        self.assertEquals(len(group.tags), 2)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = group.tags[1]

        self.assertEquals(tag[0], 'culprit')
        self.assertEquals(tag[1], 'foo.bar.zoo.baz')

        events = group.get_relations(Event)

        self.assertEquals(len(events), 1)

        event = events[0]

        self.assertEquals(event.time_spent, group.time_spent)
        self.assertEquals(event.type, group.type)
        self.assertEquals(event.date, group.last_seen)
        self.assertEquals(len(event.tags), 2)

        tag = event.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = event.tags[1]

        self.assertEquals(tag[0], 'culprit')
        self.assertEquals(tag[1], 'foo.bar.zoo.baz')

        event, group = app.client.store(
            'sentry.events.Message',
            tags=(
                ('server', 'foo.bar'),
            ),
            date=now + datetime.timedelta(seconds=1),
            time_spent=100,
            data={
                '__event__': {
                    'message': 'hello world',
                },
            },
            event_id='foobar2',
        )

        self.assertEquals(group.pk, group_id)
        self.assertEquals(group.count, 2)
        self.assertEquals(group.time_spent, 153)
        self.assertEquals(len(group.tags), 2)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = group.tags[1]

        self.assertEquals(tag[0], 'culprit')
        self.assertEquals(tag[1], 'foo.bar.zoo.baz')

        events = group.get_relations(Event, desc=False)

        self.assertEquals(len(events), 2)

        event = events[1]

        self.assertEquals(event.time_spent, 100)
        self.assertEquals(event.type, group.type)
        self.assertEquals(group.last_seen, event.date)
        self.assertEquals(len(event.tags), 1)

        tag = event.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tags = Tag.objects.order_by('-count')

        self.assertEquals(len(tags), 2, tags)

        groups = Group.objects.all()

        self.assertEquals(len(groups), 1)

        event, group = app.client.store(
            'sentry.events.Message',
            tags=(
                ('server', 'foo.bar'),
            ),
            date=now + datetime.timedelta(seconds=1),
            time_spent=100,
            data={
                '__event__': {
                    'message': 'hello world 2',
                },
            },
            event_id='foobar2',
        )

        self.assertNotEquals(group.pk, group_id)
        self.assertEquals(group.count, 1)
        self.assertEquals(group.time_spent, 100)
        self.assertEquals(len(group.tags), 1)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        events = group.get_relations(Event, desc=False)

        self.assertEquals(len(events), 1)

        event = events[0]

        self.assertEquals(event.time_spent, 100)
        self.assertEquals(event.type, group.type)
        self.assertEquals(group.last_seen, event.date)
        self.assertEquals(len(event.tags), 1)

        tag = event.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tags = Tag.objects.order_by('-count')

        self.assertEquals(len(tags), 2, tags)

        tag = tags[0]

        self.assertEquals(tag.key, 'server')
        self.assertEquals(tag.value, 'foo.bar')
        self.assertEquals(tag.count, 2)

        tag = tags[1]

        self.assertEquals(tag.key, 'culprit')
        self.assertEquals(tag.value, 'foo.bar.zoo.baz')
        self.assertEquals(tag.count, 1)

        groups = Group.objects.all()

        self.assertEquals(len(groups), 2)

    def test_message_event(self):
        event_id = capture('Message', message='foo')

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.Message')
        self.assertEquals(event.time_spent, 0)

    def test_query_event(self):
        event_id = capture('Query', query='SELECT * FROM table', engine='psycopg2', time_spent=36)

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.Query')
        self.assertEquals(event.time_spent, 36)

    def test_exception_event_without_exc_info(self):
        try:
            raise ValueError('foo bar')
        except:
            pass

        # Exception pulls in sys.exc_info()
        # by default
        event_id = capture('Exception')

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.Exception')
        self.assertEquals(event.time_spent, 0)

        data = event.data

        self.assertTrue('__event__' in data)
        event_data = data['__event__']
        self.assertTrue('value' in event_data)
        self.assertEquals(event_data['value'], 'foo bar')
        self.assertTrue('type' in event_data)
        self.assertEquals(event_data['type'], 'ValueError')
        self.assertTrue('frames' in event_data)
        self.assertEquals(len(event_data['frames']), 1)
        frame = event_data['frames'][0]
        self.assertTrue('function' in frame)
        self.assertEquals(frame['function'], 'test_exception_event_without_exc_info')
        self.assertTrue('lineno' in frame)
        self.assertTrue(frame['lineno'] > 0)
        self.assertTrue('module' in frame)
        self.assertEquals(frame['module'], 'tests.test_events')
        self.assertTrue('id' in frame)
        self.assertTrue('filename' in frame)

    def test_exception_event_with_exc_info(self):
        try:
            raise ValueError('foo bar')
        except:
            exc_info = sys.exc_info()

        # We raise a second event to ensure we actually reference
        # the first event
        try:
            raise SyntaxError('baz')
        except:
            pass

        # Exception pulls in sys.exc_info()
        # by default
        event_id = capture('Exception', exc_info=exc_info)

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.Exception')
        self.assertEquals(event.time_spent, 0)

        data = event.data

        self.assertTrue('__event__' in data)
        event_data = data['__event__']
        self.assertTrue('value' in event_data)
        self.assertEquals(event_data['value'], 'foo bar')
        self.assertTrue('type' in event_data)
        self.assertEquals(event_data['type'], 'ValueError')
        self.assertTrue('frames' in event_data)
        self.assertEquals(len(event_data['frames']), 1)
        frame = event_data['frames'][0]
        self.assertTrue('function' in frame)
        self.assertEquals(frame['function'], 'test_exception_event_with_exc_info')
        self.assertTrue('lineno' in frame)
        self.assertTrue(frame['lineno'] > 0)
        self.assertTrue('module' in frame)
        self.assertEquals(frame['module'], 'tests.test_events')
        self.assertTrue('id' in frame)
        self.assertTrue('filename' in frame)
