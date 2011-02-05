from __future__ import absolute_import

import datetime
import logging
import sys
import traceback
import urllib2
import uuid

from django.core.cache import cache
from django.template import TemplateSyntaxError
from django.views.debug import ExceptionReporter

from sentry import conf
from sentry.db import backend
from sentry.models import Event, Group, Tag, TagCount
from sentry.helpers import construct_checksum, varmap, transform, get_installed_apps, urlread, force_unicode, \
                           get_versions

class SentryClient(object):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('sentry.errors')

    def store(self, type, tags=[], data={}, date=None, time_spent=None, event_id=None):
        from sentry.models import Event, Group, Tag, TagCount

        if not date:
            date = datetime.datetime.now()

        module, class_name = type.rsplit('.', 1)

        event_processor = getattr(__import__(module, {}, {}, [class_name], -1), class_name)

        return event_processor().store(tags, data, date, time_spent, event_id)

    def send(self, **kwargs):
        "Sends the message to the server."
        if conf.REMOTE_URL:
            for url in conf.REMOTE_URL:
                data = {
                    'data': base64.b64encode(pickle.dumps(kwargs).encode('zlib')),
                    'key': conf.KEY,
                }
                try:
                    urlread(url, post=data, timeout=conf.REMOTE_TIMEOUT)
                except urllib2.HTTPError, e:
                    body = e.read()
                    logger.error('Unable to reach Sentry log server: %s (url: %%s, body: %%s)' % (e,), url, body,
                                 exc_info=True, extra={'data':{'body': body, 'remote_url': url}})
                    logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
                except urllib2.URLError, e:
                    logger.error('Unable to reach Sentry log server: %s (url: %%s)' % (e,), url,
                                 exc_info=True, extra={'data':{'remote_url': url}})
                    logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
        else:
            return self.store(**kwargs)

    # TODO: move the following into some API for events

    def create_from_record(self, record, **kwargs):
        """
        Creates an error log for a ``logging`` module ``record`` instance.
        """
        for k in ('url', 'view', 'request', 'data'):
            if k not in kwargs:
                kwargs[k] = record.__dict__.get(k)

        kwargs.update({
            'logger': record.name,
            'level': record.levelno,
            'message': force_unicode(record.msg),
            'server_name': conf.NAME,
        })

        # construct the checksum with the unparsed message
        kwargs['checksum'] = construct_checksum(**kwargs)

        # save the message with included formatting
        kwargs['message'] = record.getMessage()

        # If there's no exception being processed, exc_info may be a 3-tuple of None
        # http://docs.python.org/library/sys.html#sys.exc_info
        if record.exc_info and all(record.exc_info):
            return self.create_from_exception(record.exc_info, **kwargs)

        return self.process(
            traceback=record.exc_text,
            **kwargs
        )

class DummyClient(SentryClient):
    "Sends messages into an empty void"
    def send(self, **kwargs):
        return None
