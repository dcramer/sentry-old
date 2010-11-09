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
import logging
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from sentry import conf
from sentry.helpers import cached_property, construct_checksum, get_db_engine, transform, get_filters
from sentry.manager import GroupedMessageManager, SentryManager
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

STATUS_LEVELS = (
    (0, _('unresolved')),
    (1, _('resolved')),
)

class GzippedDictField(models.TextField):
    """
    Slightly different from a JSONField in the sense that the default
    value is a dictionary.
    """
    __metaclass__ = models.SubfieldBase
 
    def to_python(self, value):
        if isinstance(value, basestring) and value:
            value = pickle.loads(base64.b64decode(value).decode('zlib'))
        elif not value:
            return {}
        return value

    def get_prep_value(self, value):
        if value is None: return
        return base64.b64encode(pickle.dumps(transform(value)).encode('zlib'))
 
    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)

    def south_field_triple(self):
        "Returns a suitable description of this field for South."
        from south.modelsinspector import introspector
        field_class = "django.db.models.fields.TextField"
        args, kwargs = introspector(self)
        return (field_class, args, kwargs)

class Tag(models.Model):
    """
    Stores an individual tag and its checksum.
    """
    
    hash            = models.CharField(max_length=32, unique=True)
    value           = models.TextField()

    def __unicode__(self):
        return self.value

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = construct_checksum(**self.__dict__)
        super(Event, self).save(*args, **kwargs)

class TagCount(models.Model):
    """
    Stores the total number of events recorded for a combination of tags.
    """
    
    # this is md5(' '.join(tags))
    hash            = models.CharField(max_length=32, unique=True)
    tag             = models.ManyToManyField(Tag)
    count           = models.PositiveIntegerField(default=0)

class Group(models.Model):
    """
    Stores an aggregate (summary) of Event's for a combination of tags.
    """
    # XXX: do we need an m2m on Group?

    # this is the combination of md5(' '.join(tags)) + md5(event)
    hash            = models.CharField(max_length=64, unique=True)
    data            = SerializedDictField(null=True)
    status          = models.PositiveIntegerField(default=0, choices=STATUS_LEVELS, db_index=True)
    count           = models.PositiveIntegerField(default=0)
    time_spent      = models.FloatField(default=0.0)
    first_seen      = models.DateTimeField(default=datetime.datetime.now)
    last_seen       = models.DateTimeField(default=datetime.datetime.now)
    score           = models.FloatField(default=0.0, db_index=True)
    tags            = models.ManyToManyField(Tag)
    
    def save(self, *args, **kwargs):
        self.score = math.log(self.count) * 600 + int(self.last_seen)
        super(Group, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('sentry-group', (self.pk,), {})

class Event(models.Model):
    """
    An individual event. It's processor (type) handles input and output, as well as
    group summarization.
    """
    
    # the hash of this event is defined by its processor (type)
    hash            = models.CharField(max_length=32)
    type            = models.CharField(max_length=64)
    data            = GzippedDictField(null=True)
    date            = models.DateTimeField(default=datetime.datetime.now)
    tags            = models.ManyToManyField(Tag)
    
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