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
from sentry.core import slices
from sentry.utils import get_versions, transform
from sentry.utils.api import get_mac_signature, get_auth_header
from sentry.models import Tag, Group, Event

class EventProxyCache(dict):
    def __missing__(self, key):
        module, class_name = key.rsplit('.', 1)

        return getattr(__import__(module, {}, {}, [class_name], -1), class_name)

class SentryClient(object):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('sentry.errors')
        self.event_cache = EventProxyCache()

    def capture(self, event_type, tags=[], data={}, date=None, time_spent=None, event_id=None, **kwargs):
        "Captures and processes an event and pipes it off to SentryClient.send."
        if not date:
            date = datetime.datetime.now()

        if '.' not in event_type:
            # Assume it's a builtin
            event_type = 'sentry.events.%s' % event_type

        handler = self.event_cache[event_type]()

        result = handler.capture(**kwargs)

        tags = list(tags) + result['tags']

        data['__event__'] = result['data']
        
        # if request:
        #     data.update(dict(
        #         s_meta=request.META,
        #         s_post=request.POST,
        #         s_get=request.GET,
        #         s_cookies=request.COOKIES,
        #     ))
        #     tags.append(('url', request.build_absolute_uri()))

        tags.append(('server', app.config['NAME']))

        versions = get_versions()

        if '__sentry__' not in data:
            data['__sentry__'] = {}

        data['__sentry__']['versions'] = versions

        # TODO: view should probably be passable via kwargs
        if data['__sentry__'].get('culprit'):
            # get list of modules from right to left
            parts = data['__sentry__']['culprit'].split('.')
            module_list = ['.'.join(parts[:idx]) for idx in xrange(1, len(parts)+1)][::-1]
            version = None
            module = None
            for m in module_list:
                if m in versions:
                    module = m
                    version = versions[m]

            # store our "best guess" for application version
            if version:
                data['__sentry__'].update({
                    'version': version,
                    'module': module,
                })

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
        module, class_name = event_type.rsplit('.', 1)

        handler = getattr(__import__(module, {}, {}, [class_name], -1), class_name)()
        
        # Grab our tags for this event
        for k, v in tags:
            # XXX: this should be cached
            tag_hash = hashlib.md5('%s=%s' % (k, v)).hexdigest()
            tag, created = Tag.objects.get_or_create(
                hash=tag_hash,
                defaults={
                    'key': k,
                    'value': v,
                    'count': 1,
                })
            # Maintain counts
            if not created:
                tag.incr('count')

        # TODO: this should be generated from the TypeProcessor
        event_hash = hashlib.md5('|'.join(k or '' for k in handler.get_event_hash(**data['__event__']))).hexdigest()

        event = Event.objects.create(
            pk=event_id,
            type=event_type,
            hash=event_hash,
            date=date,
            time_spent=time_spent,
            tags=tags,
        )
        event.set_meta(**data)

        event_message = handler.to_string(event, data.get('__event__'))

        groups = []

        # For each view that handles this event, we need to create a Group
        for slice_ in slices.all():
            if slice_.is_valid_event(event_type):
                # # We only care about tags which are required for this view
                # event_tags = [(k, v) for k, v in tags if k in view.get('tags', [])]
                # tags_hash = TagCount.get_tags_hash(event_tags)
                # 
                # # Handle TagCount creation and incrementing
                # tc, created = TagCount.objects.get_or_create(
                #     hash=tags_hash,
                #     defaults={
                #         'tags': event_tags,
                #         'count': 1,
                #     }
                # )
                # if not created:
                #     tc.incr('count')

                group_message = event_message
                # if not view.get('labelby'):
                #     group_message = event_message
                # else:
                #     # TODO:
                group, created = Group.objects.get_or_create(
                    type=event_type,
                    hash=slice_.id + event_hash,
                    defaults={
                        'count': 1,
                        'time_spent': time_spent or 0,
                        'tags': tags,
                        'message': group_message,
                    }
                )
                if not created:
                    group.incr('count')
                    if time_spent:
                        group.incr('time_spent', time_spent)

                group.update(last_seen=event.date, score=group.get_score())

                group.add_relation(event, date.strftime('%s.%m'))

                groups.append(group)

        return event, groups

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
