from __future__ import absolute_import

import base64
import datetime
import logging
import simplejson
import time
import urllib2

from sentry import app

import sentry
from sentry.helpers import construct_checksum, force_unicode, get_signature, \
                           get_auth_header

class SentryClient(object):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('sentry.errors')

    def store(self, type, tags=[], data={}, date=None, time_spent=None, event_id=None):
        # TODO: this shouldn't be part of the client
        if not date:
            date = datetime.datetime.now()

        module, class_name = type.rsplit('.', 1)

        event_processor = getattr(__import__(module, {}, {}, [class_name], -1), class_name)

        return event_processor().store(tags, data, date, time_spent, event_id)

    def send_remote(self, url, data, headers={}):
        req = urllib2.Request(url, headers=headers)
        try:
            response = urllib2.urlopen(req, data, app.config['REMOTE_TIMEOUT']).read()
        except:
            response = urllib2.urlopen(req, data).read()
        return response

    def send(self, **kwargs):
        "Sends the message to the server."
        if app.config['REMOTE_URL']:
            for url in app.config['REMOTE_URL']:
                message = base64.b64encode(simplejson.dumps(kwargs).encode('zlib'))
                timestamp = time.time()
                signature = get_signature(message, timestamp)
                headers={
                    'Authorization': get_auth_header(signature, timestamp, '%s/%s' % (self.__class__.__name__, sentry.VERSION)),
                    'Content-Type': 'application/octet-stream',
                }
                
                try:
                    return self.send_remote(url=url, data=message, headers=headers)
                except urllib2.HTTPError, e:
                    body = e.read()
                    self.logger.error('Unable to reach Sentry log server: %s (url: %%s, body: %%s)' % (e,), url, body,
                                 exc_info=True, extra={'data':{'body': body, 'remote_url': url}})
                    self.logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
                except urllib2.URLError, e:
                    self.logger.error('Unable to reach Sentry log server: %s (url: %%s)' % (e,), url,
                                 exc_info=True, extra={'data':{'remote_url': url}})
                    self.logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
        else:
            return self.store(**kwargs)

    def create_from_record(self, record, **kwargs):
        # TODO: this should be moved into a generic LogHandlerProcessor
        """
        Creates an error log for a ``logging`` module ``record`` instance.
        """
        for k in ('url', 'view', 'request', 'data'):
            if not kwargs.get(k):
                kwargs[k] = record.__dict__.get(k)

        kwargs.update({
            'logger': record.name,
            'level': record.levelno,
            'message': force_unicode(record.msg),
            'server_name': app.config['NAME'],
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
