import datetime
import django
import logging
import warnings

from django.db import models
from django.db.models import signals

from sentry import conf
from sentry.helpers import construct_checksum

assert not conf.DATABASE_USING or django.VERSION >= (1, 2), 'The `SENTRY_DATABASE_USING` setting requires Django >= 1.2'

logger = logging.getLogger('sentry.errors')

class SentryManager(models.Manager):
    use_for_related_fields = True

    def get_query_set(self):
        qs = super(SentryManager, self).get_query_set()
        if conf.DATABASE_USING:
            qs = qs.using(conf.DATABASE_USING)
        return qs

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
        tc, created = TagCount.objects.get_or_create(
            hash=TagCount.get_tags_hash(tags),
        )
        if created:
            tc.tags = tags
        else:
            TagCount.objects.filter(pk=tc.pk).update(count=F('count') + 1)

        event = Event.objects.create(
            type=type,
            data=data,
            date=date,
        )
        event.tags = tags

        # now for each processor that handles this event we need to create a group
        mail = False
        
        group, created = Group.objects.get_or_create(
            type=type,
            hash=tc.hash + event.hash,
            defaults=dict(
            )
        )
        if not created:
            Group.objects.filter(pk=group.pk).update(
                status=0,
                count=F('count') + 1,
                time_spent=F('time_spent') + (time_spent or 0),
                last_seen=current-datetime,
            )
        else:
            group.tags = tags
            mail = True

        # except Exception, exc:
        #     # TODO: we should mail admins when there are failures
        #     try:
        #         logger.exception(u'Unable to process log entry: %s' % (exc,))
        #     except Exception, exc:
        #         warnings.warn(u'Unable to process log entry: %s' % (exc,))
        # else:
        if mail:
            group.mail_admins()
        return instance

class GroupedMessageManager(SentryManager):
    def get_by_natural_key(self, logger, view, checksum):
        return self.get(logger=logger, view=view, checksum=checksum)