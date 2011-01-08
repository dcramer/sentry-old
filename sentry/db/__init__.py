import datetime
import hashlib

VIEWS = {
    'errors': {
        'name': 'Exceptions (by Function)',
        'event': 'ExceptionEvent',
        'tags': ['func'],
        'mail': ['foo@bar.com']
    },
    'errors.urls': {
        'name': 'Exceptions (by URL)',
        'event': 'ExceptionEvent',
        'tags': ['url'],
    },
    'queries': {
        'name': 'Queries (by Function)',
        'event': 'QueryEvent',
        'tags': ['func'],
    }
}

class BaseEvent(object):
    def __init__(self, tags, data, date, time_spent):
        self.tags = tags
        self.data = data
        self.date = date
        self.time_spent = time_spent
    
    def get_id(self):
        "Returns a unique identifier for this event class."
        return '.'.join([self.__class__.__module__, self.__class__.__name__])
    
    def store(self):
        "Saves the event in the database."
        event_id = self.get_id()

        type = hashlib.md5(event_id)
    
        current_datetime = datetime.datetime.now()
    
        # Grab our tags for this event
        tags = sorted(self.tags, key=lambda x: x[0])
        for k, v in tags:
            # XXX: this should be cached
            client.incr(Tag, {'key': k, 'value': v})

        client.add(Event, {}, type=type, data=self.data, date=self.date, tags=tags)

        # For each view that handles this event, we need to create a Group
        is_new = False
        for view in VIEWS:
            if view['event'] == event_id:
                event_tags = [(k, v) for k, v in tags if k in view['tags']]
                tags_hash = TagCount.get_tags_hash(event_tags)

                # Handle TagCount creation and incrementing
                # TODO: define use case for TagCount
                client.incr(TagCount, {'hash': tags_hash}, 'count')
                client.add(TagCount, {'hash': tags_hash}, tags=event_tags)

                if not client.add(Group, {'type': type, 'hash': tags_hash + event.hash}, tags=tags):
                    client.incr(Group, {'type': type, 'hash': tags_hash + event.hash}, 'count')
                    if time_spent:
                        client.incr(Group, {'type': type, 'hash': tags_hash + event.hash}, 'time_spent', time_spent)
                    client.set(Group, {'type': type, 'hash': tags_hash + event.hash}, status=0, last_seen=current_datetime)
                    is_new = True