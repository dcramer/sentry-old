from __future__ import absolute_import

import datetime
import hashlib

from sentry import app
from sentry.db import models
from sentry.utils.compat import math

class Group(models.Model):
    """
    Stores an aggregate (summary) of Event's for a combination of tags
    given a slice.
    """

    # key is (type, hash)

    # this is the combination of md5(' '.join(tags)) + md5(event)
    type            = models.String() # length 32
    hash            = models.String() # length 32
    # one line summary used for rendering
    message         = models.String()
    state           = models.Integer(default=0)
    count           = models.Integer(default=0)
    score           = models.Float(default=0.0)
    time_spent      = models.Integer(default=0)
    first_seen      = models.DateTime(default=datetime.datetime.now)
    last_seen       = models.DateTime(default=datetime.datetime.now)
    # This is a meta element which needs magically created or something
    # score           = models.Float(default=0.0)
    tags            = models.List()

    class Meta:
        ordering = 'last_seen'
        sortables = ('time_spent', 'first_seen', 'last_seen', 'score')
        indexes = (('type', 'hash'),)

    def save(self, *args, **kwargs):
        created = not self.pk
        self.score = self.get_score()
        super(Group, self).save(*args, **kwargs)
        if created:
            EventType.add_group(self)
            Tag.add_group(self)

    def delete(self, *args, **kwargs):
        super(Group, self).delete(*args, **kwargs)
        EventType.remove_group(self)
        Tag.remove_group(self)

    def get_score(self):
        return float(abs(math.log(self.count) * 600 + float(self.last_seen.strftime('%s.%m'))))

class Event(models.Model):
    """
    An individual event. It's processor (type) handles input and output, as well as
    group summarization.
    """

    # the hash of this event is defined by its processor (type)
    hash            = models.String()
    type            = models.String()
    date            = models.DateTime(default=datetime.datetime.now)
    time_spent      = models.Integer(default=0) # in ms
    tags            = models.List()

    class Meta:
        ordering = 'date'

    def get_version(self):
        if not self.data:
            return
        if 'version' not in self.data:
            return
        return self.data['version']

    def get_processor(self):
        mod_name, class_name = self.type.rsplit('.', 1)
        processor = getattr(__import__(mod_name, {}, {}, [class_name]), class_name)()
        return processor

class EventType(models.Model):
    """
    Stores a list of all event types seen, as well as
    a tally of the number of events recorded.
    """
    # full module path to Event class, e.g. sentry.events.Exception
    path            = models.String()
    # number of unique groups seen for this event
    count           = models.Integer(default=0)

    class Meta:
        ordering = 'count'
        indexes = (('path',),)

    def __unicode__(self):
        return self.path

    @classmethod
    def add_group(cls, group):
        et, created = cls.objects.get_or_create(
            path=group.type,
            defaults={
                'count': 1,
            }
        )
        if not created:
            et.incr('count', 1)
    
    @classmethod
    def remove_group(cls, group):
        try:
            et = cls.objects.get(path=group.type)
        except EventType.DoesNotExist:
            return

        et.decr('count', 1)
        if et.count <= 0:
            et.delete()

class Tag(models.Model):
    """
    Stores a unique value of a tag.
    """

    key             = models.String() # length 16?
    # hash is md5('key=value')
    hash            = models.String() # length 32
    value           = models.String()
    count           = models.Integer(default=0)

    class Meta:
        ordering = 'count'
        indexes = (('hash',), ('key',))

    def __unicode__(self):
        return u"%s=%s; count=%s" % (self.key, self.value, self.count)

    @classmethod
    def add_group(cls, group):
        for key, value in group.tags:
            hash = hashlib.md5(u'%s=%s' % (key, value)).hexdigest()
            tag, created = cls.objects.get_or_create(
                hash=hash,
                defaults={
                    'key': key,
                    'value': value,
                    'count': 1,
                }
            )
            if not created:
                tag.incr('count', 1)
    
    @classmethod
    def remove_group(cls, group):
        for key, value in group.tags:
            try:
                tag = cls.objects.get(hash=hash)
            except cls.DoesNotExist:
                continue

            tag.decr('count', 1)
            if tag.count <= 0:
                tag.delete()
