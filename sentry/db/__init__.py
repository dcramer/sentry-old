import hashlib

def save_event(processor, tags, data, date=None, time_spent=None):
    type = hashlib.md5('%s.%s' (processor.__module__, processor.__name__))
    
    current_datetime = datetime.datetime.now()
    
    # Grab our tags for this event
    tags = sorted(kwargs.pop('tags', {}).items(), key=lambda x: x[0])
    for k, v in tags:
        # XXX: this should be cached
        client.incr(Tag, {'key': k, 'value': v})

    tags_hash = TagCount.get_tags_hash(tags)

    # Handle TagCount creation and incrementing
    client.incr(TagCount, {'hash': tags_hash}, 'count')
    client.add(TagCount, {'hash': tags_hash}, tags=tags)
    client.add(Event, {}, type=type, data=data, date=date, tags=tags)

    # now for each processor that handles this event we need to create a group
    if not client.add(Group, {'type': type, 'hash': tc.hash + event.hash}, tags=tags):
        client.incr(Group, {'type': type, 'hash': tc.hash + event.hash}, 'count')
        if time_spent:
            client.incr(Group, {'type': type, 'hash': tc.hash + event.hash}, 'time_spent', time_spent)
        client.set(Group, {'type': type, 'hash': tc.hash + event.hash}, status=0, last_seen=current_datetime)
        mail = False
    else:
        mail = True

    if mail:
        group.mail_admins()
