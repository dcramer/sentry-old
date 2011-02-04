import base64
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    import cmath as math
except ImportError:
    import math
import datetime
import hashlib
import logging
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from sentry import conf
from sentry.db import models, backend
from sentry.helpers import cached_property, construct_checksum, get_db_engine, transform, get_filters
from sentry.reporter import FakeRequest

_reqs = ('paging',)
for r in _reqs:
    if r not in settings.INSTALLED_APPS:
        raise ImproperlyConfigured("Put '%s' in your "
            "INSTALLED_APPS setting in order to use the sentry application." % r)

from indexer.models import Index

try:
    from idmapper.models import SharedMemoryModel as Model
except ImportError:
    Model = models.Model

__all__ = ('Message', 'GroupedMessage')

class Tag(models.Model):
    """
    Stores a unique value of a tag.
    """

    key             = models.String() # length 16?
    hash            = models.String() # length 32
    value           = models.String()
    count           = models.Integer(default=0)

    class Meta:
        unique_together = (('key', 'hash'),)

    def __unicode__(self):
        return u"%s=%s" % (self.tag, self.value)

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = hashlib.md5(self.value).hexdigest()
        super(Tag, self).save(*args, **kwargs)

class TagCount(models.Model):
    """
    Stores the total number of events recorded for a combination of tags.
    """

    # this is md5(' '.join(tags))
    hash            = models.String() # length 32
    count           = models.Integer(default=0)

    # M2M on tags

    @classmethod
    def get_tags_hash(cls, tags):
        return hashlib.md5(' '.join('='.join(t) for t in tags)).hexdigest()

class Group(models.Model):
    """
    Stores an aggregate (summary) of Event's for a combination of tags.
    """

    # key is (type, hash)

    # this is the combination of md5(' '.join(tags)) + md5(event)
    type            = models.String() # length 32
    hash            = models.String() # length 64
    # one line summary used for rendering
    message         = models.String()
    state           = models.Integer(default=0)
    count           = models.Integer(default=0)
    time_spent      = models.Integer(default=0)
    first_seen      = models.DateTime(default=datetime.datetime.now)
    last_seen       = models.DateTime(default=datetime.datetime.now)
    # This is a meta element which needs magically created or something
    # score           = models.Float(default=0.0)

    # M2M on tags

    def save(self, *args, **kwargs):
        self.score = math.log(self.count) * 600 + int(self.last_seen)
        super(Group, self).save(*args, **kwargs)

class Event(models.Model):
    """
    An individual event. It's processor (type) handles input and output, as well as
    group summarization.

    Any field that isnt declared is assumed a text type.
    """

    # the hash of this event is defined by its processor (type)
    hash            = models.String()
    type            = models.String()
    date            = models.DateTime(default=datetime.datetime.now)
    time_spent      = models.Integer(default=0) # in ms
    # XXX: possibly need to store this completely denormalized so its:
    # [(tag, value), (tag, value)]

    # M2M on tags

    class Meta:
        unique_together = (('hash', 'type'),)

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = construct_checksum(**self.__dict__)
        super(Event, self).save(*args, **kwargs)

    def mail_admins(self, request=None, fail_silently=True):
        if not conf.ADMINS:
            return

        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        message = self.message_set.order_by('-id')[0]

        obj_request = message.request

        subject = 'Error (%s IP): %s' % ((obj_request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS and 'internal' or 'EXTERNAL'), obj_request.path)
        if message.site:
            subject  = '[%s] %s' % (message.site, subject)
        try:
            request_repr = repr(obj_request)
        except:
            request_repr = "Request repr() unavailable"

        if request:
            link = request.build_absolute_url(self.get_absolute_url())
        else:
            link = '%s%s' % (conf.URL_PREFIX, self.get_absolute_url())

        body = render_to_string('sentry/emails/error.txt', {
            'request_repr': request_repr,
            'request': obj_request,
            'group': self,
            'traceback': message.traceback,
            'link': link,
        })

        send_mail(subject, body,
                  settings.SERVER_EMAIL, conf.ADMINS,
                  fail_silently=fail_silently)

class RequestEvent(object):
    def __init__(self, data):
        self.data = data

    @cached_property
    def request(self):
        fake_request = FakeRequest()
        fake_request.META = self.data.get('META', {})
        fake_request.GET = self.data.get('GET', {})
        fake_request.POST = self.data.get('POST', {})
        fake_request.FILES = self.data.get('FILES', {})
        fake_request.COOKIES = self.data.get('COOKIES', {})
        fake_request.url = self.url
        if self.url:
            fake_request.path_info = '/' + self.url.split('/', 3)[-1]
        else:
            fake_request.path_info = ''
        fake_request.path = fake_request.path_info
        return fake_request
