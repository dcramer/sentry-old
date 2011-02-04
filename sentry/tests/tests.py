import unittest2
import datetime

from sentry.client import client
from sentry.db import backend
from sentry.models import Event, Tag, Group

class SentryTest(unittest2.TestCase):
    def setUp(self):
        # TODO: this should change schemas, or something
        backend.conn.flushdb()

    # Some quick ugly high level tests to get shit working fast
    def test_create(self):
        # redis is so blazing fast that we have to artificially inflate dates
        # or tests wont pass :)
        now = datetime.datetime.now()

        group = client.create(
            type='exception',
            tags=(
                ('server', 'foo.bar'),
                ('view', 'foo.bar.zoo.baz'),
            ),
            date=now,
            time_spent=53,
        )
        self.assertTrue(group.pk)
        self.assertEquals(group.type, 'exception')
        self.assertEquals(group.time_spent, 53)
        self.assertEquals(group.count, 1)
        self.assertEquals(len(group.tags), 2)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = group.tags[1]

        self.assertEquals(tag[0], 'view')
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

        self.assertEquals(tag[0], 'view')
        self.assertEquals(tag[1], 'foo.bar.zoo.baz')

        group = client.create(
            type='exception',
            tags=(
                ('server', 'foo.bar'),
            ),
            date=now + datetime.timedelta(seconds=1),
            time_spent=100,
        )

        self.assertEquals(group.count, 2)
        self.assertEquals(group.time_spent, 153)
        self.assertEquals(len(group.tags), 2)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = group.tags[1]

        self.assertEquals(tag[0], 'view')
        self.assertEquals(tag[1], 'foo.bar.zoo.baz')

        events = group.get_relations(Event)

        self.assertEquals(len(events), 2)

        event = events[1]

        self.assertEquals(event.time_spent, 100)
        self.assertEquals(event.type, group.type)
        self.assertEquals(group.last_seen, event.date)
        self.assertEquals(len(event.tags), 1)

        tag = event.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tags = Tag.objects.sort_by('-count')

        self.assertEquals(len(tags), 2)

        tag = tags[0]

        self.assertEquals(tag.key, 'server')
        self.assertEquals(tag.value, 'foo.bar')
        self.assertEquals(tag.count, 2)

        tag = tags[1]

        self.assertEquals(tag.key, 'view')
        self.assertEquals(tag.value, 'foo.bar.zoo.baz')
        self.assertEquals(tag.count, 1)

        groups = Group.objects.all()

        self.assertEquals(len(groups), 1)
