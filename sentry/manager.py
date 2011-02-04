import datetime
import django
import logging
import warnings

from sentry import conf
from sentry.db import models
from sentry.helpers import construct_checksum

assert not conf.DATABASE_USING or django.VERSION >= (1, 2), 'The `SENTRY_DATABASE_USING` setting requires Django >= 1.2'

logger = logging.getLogger('sentry.errors')

class SentryManager(models.Manager):
    def from_kwargs(self, type, tags, data=None, date=None, time_spent=None):
        from sentry.models import Event, Group, Tag, TagCount

        current_datetime = datetime.datetime.now()

        # Grab our tags for this event
        tags = []
        for k, v in sorted(kwargs.pop('tags', {}).items(), key=lambda x: x[0]):
            # XXX: this should be cached
            tag, created = Tag.objects.get_or_create(key=k, value=v)
            tags.append(tag)
            # Maintain counts
            if not created:
                Tag.objects.filter(pk=tag.pk).update(count=F('count') + 1)

        # Handle TagCount creation and incrementing
        tc = TagCount.objects.get(TagCount.get_tags_hash(tags))
        if tc.count == 0:
            tc.update(tags=tags)
            tc.incr(count)

        event = Event.objects.create(
            type=type,
            date=date,
            time_spent=time_spent,
            tags=tags,
            **data
        )

        group = Group.objects.get_or_create('%s:%s:%s' % (type, tc.hash, event.hash))
        group.incr('count')
        if time_spent:
            group.incr('time_spent', time_spent)
        group.update(last_seen=current_datetime, tags=tags)

        group.add_relation(event, date)

        # TODO: This logic should be some kind of "on-field-change" hook
        backend.index(Group, group.pk, 'date', group.date)
        backend.index(Group, group.pk, 'time_spent', group.time_spent)
        backend.index(Group, group.pk, 'count', group.count)

        return group