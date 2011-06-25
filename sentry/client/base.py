from __future__ import absolute_import

import base64
import datetime
import hashlib
import logging
import simplejson
import time
import uuid
import urllib2

from sentry import app

import sentry
from sentry.utils import get_versions, transform
from sentry.utils.api import get_mac_signature, get_auth_header
from sentry.models import Group, Event

class ModuleProxyCache(dict):
    def __missing__(self, key):
        module, class_name = key.rsplit('.', 1)

        handler = getattr(__import__(module, {}, {}, [class_name], -1), class_name)
        
        self[key] = handler
        
        return handler

class SentryClient(object):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('sentry.errors')
        self.module_cache = ModuleProxyCache()

    def capture(self, event_type, tags=[], data={}, date=None, time_spent=None, event_id=None,
                extra={}, culprit=None, **kwargs):
        """
        Captures and processes an event and pipes it off to SentryClient.send.
        
        To use structured data (interfaces) with capture:
        
        >>> capture('Message', message='foo', data={
        >>>     'sentry.core.interfaces.Http': {
        >>>         'url': '...',
        >>>         'data': {},
        >>>         'querystring': '...',
        >>>         'method': 'POST',
        >>>     },
        >>> })
        
        :param event_type: the module path to the Event class. Builtins can use shorthand class
                           notation and exclude the full module path.
        :param tags: a list of tuples (key, value) specifying additional tags for event
        :param data: the data base, useful for specifying structured data interfaces. Any key which contains a '.'
                     will be assumed to be a data interface.
        :param date: the datetime of this event
        :param time_spent: a float value representing the duration of the event
        :param event_id: a 32-length unique string identifying this event
        :param extra: a dictionary of additional standard metadata
        :param culprit: a string representing the cause of this event (generally a path to a function)
        :return: a 32-length string identifying this event
        """
        if not date:
            date = datetime.datetime.now()

        if '.' not in event_type:
            # Assume it's a builtin
            event_type = 'sentry.events.%s' % event_type

        handler = self.module_cache[event_type]()

        result = handler.capture(**kwargs)

        tags = list(tags) + result['tags']

        data['extra'] = extra
        data['event'] = result['data']
        
        if not culprit:
            culprit = result.get('culprit')
        
        for k, v in kwargs.iteritems():
            if '.' not in k:
                continue

            interface = self.module_cache[k]
            data[k] = interface(**v).serialize()
        
        tags.append(('server', app.config['NAME']))

        versions = get_versions()

        data['modules'] = versions

        if culprit:
            data['culprit'] = culprit

            # get list of modules from right to left
            parts = culprit.split('.')
            module_list = ['.'.join(parts[:idx]) for idx in xrange(1, len(parts)+1)][::-1]
            version = None
            module = None
            for m in module_list:
                if m in versions:
                    module = m
                    version = versions[m]

            # store our "best guess" for application version
            if version:
                data['version'] = (module, version),

        # TODO: Cache should be handled by the db backend by default (as we expect a fast access backend)
        # if app.config['THRASHING_TIMEOUT'] and app.config['THRASHING_LIMIT']:
        #     cache_key = 'sentry:%s:%s' % (kwargs.get('class_name') or '', checksum)
        #     added = cache.add(cache_key, 1, app.config['THRASHING_TIMEOUT'])
        #     if not added:
        #         try:
        #             thrash_count = cache.incr(cache_key)
        #         except (KeyError, ValueError):
        #             # cache.incr can fail. Assume we aren't thrashing yet, and
        #             # if we are, hope that the next error has a successful
        #             # cache.incr call.
        #             thrash_count = 0
        #         if thrash_count > app.config['THRASHING_LIMIT']:
        #             return

        # for filter_ in get_filters():
        #     kwargs = filter_(None).process(kwargs) or kwargs

        # create ID client-side so that it can be passed to application
        event_id = uuid.uuid4().hex

        # Make sure all data is coerced
        data = transform(data)

        self.send(event_type=event_type, tags=tags, data=data, date=date, time_spent=time_spent, event_id=event_id)

        return event_id

    def store(self, event_type, tags, data, date, time_spent, event_id, **kwargs):
        """
        Saves a new event to the datastore.
        """
        module, class_name = event_type.rsplit('.', 1)

        handler = getattr(__import__(module, {}, {}, [class_name], -1), class_name)()

        event_hash = hashlib.md5('|'.join(k or '' for k in handler.get_event_hash(**data['event']))).hexdigest()

        event = Event.objects.create(
            pk=event_id,
            type=event_type,
            hash=event_hash,
            date=date,
            time_spent=time_spent,
            tags=tags,
        )
        event.set_meta(**data)

        event_message = handler.to_string(event, data.get('event'))

        group, created = Group.objects.get_or_create(
            type=event_type,
            hash=event_hash,
            defaults={
                'count': 1,
                'time_spent': time_spent or 0,
                'tags': tags,
                'message': event_message,
            }
        )
        if not created:
            group.incr('count')
            if time_spent:
                group.incr('time_spent', time_spent)

        group.update(last_seen=event.date, score=group.get_score())

        group.add_relation(event, date.strftime('%s.%m'))

        # TODO: we need to manually add indexes per sort+filter value pair

        return event, group

    def send_remote(self, url, data, headers={}):
        req = urllib2.Request(url, headers=headers)
        try:
            response = urllib2.urlopen(req, data, app.config['REMOTE_TIMEOUT']).read()
        except:
            response = urllib2.urlopen(req, data).read()
        return response

    def send(self, **kwargs):
        "Sends the message to the server."
        if app.config['REMOTES']:
            for url in app.config['REMOTES']:
                message = base64.b64encode(simplejson.dumps(kwargs).encode('zlib'))
                timestamp = time.time()
                nonce = uuid.uuid4().hex
                signature = get_mac_signature(app.config['KEY'], message, nonce, timestamp)
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

class DummyClient(SentryClient):
    "Sends events into an empty void"
    def send(self, **kwargs):
        return None
