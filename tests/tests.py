import datetime
import sys
import unittest2

from sentry import app
from sentry.db import get_backend, models
from sentry.events import store
from sentry.models import Event, Tag, Group

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

class TestModel(models.Model):
    str_ = models.String()
    int_ = models.Integer()
    float_ = models.Float()
    list_ = models.List()
    
    class Meta:
        sortables = ('int_', 'float_')
        indexes = (('str_',),)
    
class ORMTest(BaseTest):
    def test_create(self):
        inst = TestModel.objects.create(
            str_='foo',
            int_=0,
            float_=0.1,
            list_=[1, 2, 3],
        )
        self.assertEquals(TestModel.objects.count(), 1)
        self.assertTrue(inst.pk)
        self.assertEquals(inst.str_, 'foo')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.1)
        self.assertEquals(len(inst.list_), 3)
        self.assertTrue(1 in inst.list_)
        self.assertTrue(2 in inst.list_)
        self.assertTrue(3 in inst.list_)

    def test_get_or_create(self):
        inst, created = TestModel.objects.get_or_create(str_='foo', defaults={
            'int_': 0,
            'float_': 0.1,
            'list_': [1, 2, 3],
        })
        self.assertTrue(created)
        self.assertEquals(TestModel.objects.count(), 1)
        self.assertTrue(inst.pk)
        self.assertEquals(inst.str_, 'foo')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.1)
        self.assertEquals(len(inst.list_), 3)
        self.assertTrue(1 in inst.list_)
        self.assertTrue(2 in inst.list_)
        self.assertTrue(3 in inst.list_)

        inst, created = TestModel.objects.get_or_create(str_='foo', defaults={
            'int_': 1,
            'float_': 1.1,
            'list_': [1],
        })
        self.assertFalse(created)
        self.assertEquals(TestModel.objects.count(), 1)
        self.assertTrue(inst.pk)
        self.assertEquals(inst.str_, 'foo')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.1)
        self.assertTrue(len(inst.list_), 3)
        self.assertTrue(1 in inst.list_)
        self.assertTrue(2 in inst.list_)
        self.assertTrue(3 in inst.list_)

    def test_get(self):
        self.assertEquals(TestModel.objects.count(), 0)

        self.assertRaises(TestModel.DoesNotExist, TestModel.objects.get, 'foo')

        inst = TestModel.objects.create(str_='foo')

        self.assertEquals(TestModel.objects.count(), 1)

        self.assertEquals(TestModel.objects.get(inst.pk), inst)

    def test_delete(self):
        self.assertEquals(TestModel.objects.count(), 0)

        inst = TestModel.objects.create(str_='foo')

        self.assertEquals(TestModel.objects.count(), 1)
        
        inst.delete()

        self.assertEquals(TestModel.objects.count(), 0)

        self.assertRaises(TestModel.DoesNotExist, TestModel.objects.get, 'foo')

    def test_saving_behavior(self):
        self.assertEquals(TestModel.objects.count(), 0)

        inst = TestModel()
        
        self.assertFalse(inst.pk)
        
        self.assertEquals(TestModel.objects.count(), 0)
        
        inst.save()
        
        self.assertTrue(inst.pk)
        self.assertEquals(TestModel.objects.count(), 1)
        self.assertEquals(TestModel.objects.get(inst.pk), inst)

        self.assertEquals(inst.str_, '')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.0)
        self.assertEquals(len(inst.list_), 0)
        
        inst.update(str_='foo')

        self.assertEquals(TestModel.objects.count(), 1)
        self.assertEquals(inst.str_, 'foo')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.0)
        self.assertEquals(len(inst.list_), 0)
        
        inst = TestModel.objects.get(pk=inst.pk)

        self.assertEquals(inst.str_, 'foo')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 0.0)
        self.assertEquals(len(inst.list_), 0)

        inst = TestModel(float_=1.0)
        
        self.assertFalse(inst.pk)
        
        inst.save()

        self.assertEquals(TestModel.objects.count(), 2)
        
        self.assertEquals(inst.str_, '')
        self.assertEquals(inst.int_, 0)
        self.assertEquals(inst.float_, 1.0)
        self.assertEquals(len(inst.list_), 0)

class SentryTest(BaseTest):
    # Some quick ugly high level tests to get shit working fast
    def test_create(self):
        # redis is so blazing fast that we have to artificially inflate dates
        # or tests wont pass :)
        now = datetime.datetime.now()

        event, groups = app.client.store(
            type='sentry.events.MessageEvent',
            tags=(
                ('server', 'foo.bar'),
                ('view', 'foo.bar.zoo.baz'),
            ),
            date=now,
            time_spent=53,
            data={
                '__event__': {
                    'msg_value': 'hello world',
                }
            }
        )
        self.assertEquals(len(groups), 1)

        group = groups[0]
        group_id = group.pk

        self.assertTrue(group.pk)
        self.assertEquals(group.type, 'sentry.events.MessageEvent')
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

        event, groups = app.client.store(
            type='sentry.events.MessageEvent',
            tags=(
                ('server', 'foo.bar'),
            ),
            date=now + datetime.timedelta(seconds=1),
            time_spent=100,
            data={
                '__event__': {
                    'msg_value': 'hello world',
                },
            }
        )

        self.assertEquals(len(groups), 1)

        group = groups[0]

        self.assertEquals(group.pk, group_id)
        self.assertEquals(group.count, 2)
        self.assertEquals(group.time_spent, 153)
        self.assertEquals(len(group.tags), 2)

        tag = group.tags[0]

        self.assertEquals(tag[0], 'server')
        self.assertEquals(tag[1], 'foo.bar')

        tag = group.tags[1]

        self.assertEquals(tag[0], 'view')
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

    def test_message_event(self):
        event_id = store('MessageEvent', 'foo')

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.MessageEvent')
        self.assertEquals(event.time_spent, 0)

    def test_exception_event_without_exc_info(self):
        try:
            raise ValueError('foo bar')
        except:
            pass

        # ExceptionEvent pulls in sys.exc_info()
        # by default
        event_id = store('ExceptionEvent')

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.ExceptionEvent')
        self.assertEquals(event.time_spent, 0)

        data = event.data

        self.assertTrue('__event__' in data)
        event_data = data['__event__']
        self.assertTrue('exc_value' in event_data)
        self.assertEquals(event_data['exc_value'], 'foo bar')
        self.assertTrue('exc_type' in event_data)
        self.assertEquals(event_data['exc_type'], 'ValueError')
        self.assertTrue('exc_frames' in event_data)
        self.assertEquals(len(event_data['exc_frames']), 1)
        frame = event_data['exc_frames'][0]
        self.assertTrue('function' in frame)
        self.assertEquals(frame['function'], 'test_exception_event_without_exc_info')
        self.assertTrue('lineno' in frame)
        self.assertTrue(frame['lineno'] > 0)
        self.assertTrue('module' in frame)
        self.assertEquals(frame['module'], 'tests.tests')
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

        # ExceptionEvent pulls in sys.exc_info()
        # by default
        event_id = store('ExceptionEvent', exc_info=exc_info)

        event = Event.objects.get(event_id)

        self.assertEquals(event.type, 'sentry.events.ExceptionEvent')
        self.assertEquals(event.time_spent, 0)

        data = event.data

        self.assertTrue('__event__' in data)
        event_data = data['__event__']
        self.assertTrue('exc_value' in event_data)
        self.assertEquals(event_data['exc_value'], 'foo bar')
        self.assertTrue('exc_type' in event_data)
        self.assertEquals(event_data['exc_type'], 'ValueError')
        self.assertTrue('exc_frames' in event_data)
        self.assertEquals(len(event_data['exc_frames']), 1)
        frame = event_data['exc_frames'][0]
        self.assertTrue('function' in frame)
        self.assertEquals(frame['function'], 'test_exception_event_with_exc_info')
        self.assertTrue('lineno' in frame)
        self.assertTrue(frame['lineno'] > 0)
        self.assertTrue('module' in frame)
        self.assertEquals(frame['module'], 'tests.tests')
        self.assertTrue('id' in frame)
        self.assertTrue('filename' in frame)
