import unittest2

from sentry.models import Event
from sentry.client import client

class SentryTest(unittest2.TestCase):
    # Some quick ugly high level tests to get shit working fast
    def test_create(self):
        group = client.create(
            type='exception',
            tags=(
                ('server', 'foo.bar'),
                ('view', 'foo.bar.zoo.baz'),
            ),
            time_spent=53,
        )
        self.assertTrue(group.pk)
        self.assertEquals(group.type, 'exception')
        self.assertEquals(group.time_spent, 53)
        self.assertEquals(group.count, 1)

        events = group.get_relations(Event)

        self.assertEquals(len(events), 1)

        event = events[0]

        print event.__dict__

        self.assertEquals(event.time_spent, group.time_spent)
        self.assertEquals(event.type, group.type)
        self.assertEquals(event.date, group.last_seen)
