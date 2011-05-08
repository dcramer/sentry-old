from __future__ import absolute_import

try:
    import cmath as math
except ImportError:
    import math
import datetime
import hashlib

from sentry import app
from sentry.db import models
from sentry.utils import cached_property, MockRequest

class Tag(models.Model):
    """
    Stores a unique value of a tag.
    """

    key             = models.String() # length 16?
    hash            = models.String() # length 32
    value           = models.String()
    count           = models.Integer(default=0)

    class Meta:
        ordering = 'count'

    def __unicode__(self):
        return u"%s=%s; count=%s" % (self.key, self.value, self.count)

class TagCount(models.Model):
    """
    Stores the total number of events recorded for a combination of tags.
    """

    # this is md5(' '.join(tags))
    hash            = models.String() # length 32
    count           = models.Integer(default=0)
    tags            = models.List()

    class Meta:
        ordering = 'count'

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
    score           = models.Integer(default=0)
    time_spent      = models.Integer(default=0)
    first_seen      = models.DateTime(default=datetime.datetime.now)
    last_seen       = models.DateTime(default=datetime.datetime.now)
    # This is a meta element which needs magically created or something
    # score           = models.Float(default=0.0)
    tags            = models.List()

    class Meta:
        ordering = 'last_seen'
        indexes = ('time_spent', 'first_seen', 'last_seen')

    def save(self, *args, **kwargs):
        self.score = self.get_score()
        super(Group, self).save(*args, **kwargs)

    def get_score(self):
        return int(math.log(self.count) * 600 + int(self.last_seen.strftime('%s')))

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
    # XXX: possibly need to store this completely denormalized so its:
    # [(tag, value), (tag, value)]

    class Meta:
        ordering = 'date'

    def mail_admins(self, request=None, fail_silently=True):
        if not app.config['ADMINS']:
            return

        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        message = self.message_set.order_by('-id')[0]

        obj_request = message.request

        subject = 'Error (%s IP): %s' % (obj_request.META.get('REMOTE_ADDR'), obj_request.path)
        if message.site:
            subject  = '[%s] %s' % (message.site, subject)
        try:
            request_repr = repr(obj_request)
        except:
            request_repr = "Request repr() unavailable"

        if request:
            link = request.build_absolute_url(self.get_absolute_url())
        else:
            link = '%s%s' % (app.config['URL_PREFIX'], self.get_absolute_url())

        body = render_to_string('sentry/emails/error.txt', {
            'request_repr': request_repr,
            'request': obj_request,
            'group': self,
            'traceback': message.traceback,
            'link': link,
        })

        send_mail(subject, body,
                  app.config['SERVER_EMAIL'], app.config['ADMINS'],
                  fail_silently=fail_silently)

    def get_version(self):
        if not self.data:
            return
        if '__sentry__' not in self.data:
            return
        if 'version' not in self.data['__sentry__']:
            return
        module = self.data['__sentry__'].get('module', 'ver')
        return module, self.data['__sentry__']['version']

class RequestEvent(object):
    def __init__(self, data):
        self.data = data

    @cached_property
    def request(self):
        fake_request = MockRequest(
            META = self.data.get('META') or {},
            GET = self.data.get('GET') or {},
            POST = self.data.get('POST') or {},
            FILES = self.data.get('FILES') or {},
            COOKIES = self.data.get('COOKIES') or {},
            url = self.url,
        )
        if self.url:
            fake_request.path_info = '/' + self.url.split('/', 3)[-1]
        else:
            fake_request.path_info = ''
        fake_request.path = fake_request.path_info
        return fake_request
