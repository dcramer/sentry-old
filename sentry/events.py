import datetime
import hashlib

from sentry import conf
from sentry.models import TagCount, Tag, Group, Event

class BaseEvent(object):
    def get_id(self):
        "Returns a unique identifier for this event class."
        return '.'.join([self.__class__.__module__, self.__class__.__name__])

    def store(self, tags, data, date=None, time_spent=None):
        "Saves the event in the database."
        event_id = self.get_id()

        if not date:
            date = datetime.datetime.now()

        # Grab our tags for this event
        for k, v in tags:
            # XXX: this should be cached
            tag, created = Tag.objects.get_or_create(
                key=k,
                value=v,
                defaults={
                    'count': 1,
                })
            # Maintain counts
            if not created:
                tag.incr('count')
            Tag.objects.add_to_index(tag.pk, 'count', int(tag.count))

        # XXX: We need some special handling for "data" as it shouldnt be part of the main hash??

        # TODO: this should be generated from the TypeProcessor
        event_hash = hashlib.md5('|'.join(self.get_event_id(**data))).hexdigest()

        event = Event.objects.create(
            type=event_id,
            hash=event_hash,
            date=date,
            time_spent=time_spent,
            tags=tags,
        )
        event.set_meta(**data)

        groups = []

        # For each view that handles this event, we need to create a Group
        for view in conf.VIEWS.itervalues():
            if view['event'] == event_id:
                # We only care about tags which are required for this view

                event_tags = [(k, v) for k, v in tags if k in view.get('tags', [])]
                tags_hash = TagCount.get_tags_hash(event_tags)

                # Handle TagCount creation and incrementing
                tc, created = TagCount.objects.get_or_create(
                    hash=tags_hash,
                    defaults={
                        'tags': tags,
                        'count': 1,
                    }
                )
                if not created:
                    tc.incr('count')

                group, created = Group.objects.get_or_create(
                    type=event_id,
                    hash=tags_hash + event_hash,
                    defaults={
                        'count': 1,
                        'time_spent': time_spent,
                        'tags': tags,
                    }
                )
                if not created:
                    group.incr('count')
                    if time_spent:
                        group.incr('time_spent', time_spent)
                group.update(last_seen=event.date)

                group.add_relation(event, date.strftime('%s.%m'))

                groups.append(group)

        return event, groups

class MessageEvent(BaseEvent):
    """
    Messages store the following metadata:

    - msg_value: 'My message'
    """
    def get_event_id(self, msg_value=None, **kwargs):
        return [msg_value]

class ExceptionEvent(BaseEvent):
    """
    Exceptions store the following metadata:

    - exc_value: 'My exception value'
    - exc_type: 'module.ClassName'
    - exc_frames: [(line number, line text, filename, truncated locals)]
    """
    def get_event_id(self, exc_value=None, exc_type=None, exc_frames=None, **kwargs):
        return [exc_value, exc_type]

class SQLEvent(BaseEvent):
    """
    Messages store the following metadata:

    - sql_value: 'SELECT * FROM table'
    - sql_engine: 'postgesql_psycopg2'
    """
    def get_event_id(self, sql_value=None, sql_engine=None, **kwargs):
        return [sql_value, sql_engine]
