import base64
try:
    import cPickle as pickle
except ImportError:
    import pickle
import datetime
import logging
import sys
import traceback
import urllib2

from django.core.cache import cache
from django.template import TemplateSyntaxError
from django.views.debug import ExceptionReporter

from sentry import conf
from sentry.db import backend
from sentry.models import Event, Group, Tag, TagCount
from sentry.helpers import construct_checksum, varmap, transform, get_installed_apps, urlread, force_unicode

class SentryClient(object):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('sentry.errors')

    def create(self, type, tags, data={}, date=None, time_spent=None):
        from sentry.models import Event, Group, Tag, TagCount

        if not date:
            date = datetime.datetime.now()

        # Grab our tags for this event
        for k, v in tags:
            # XXX: this should be cached
            tag, created = Tag.objects.get_or_create(
                key=k,
                value=v,
                defaults={
                    'count': 1,
                })
            # Maintain counts
            if not created:
                tag.incr('count')
            Tag.objects.add_to_index(tag.pk, 'count', int(tag.count))

        # Handle TagCount creation and incrementing
        tc, created = TagCount.objects.get_or_create(
            hash=TagCount.get_tags_hash(tags),
            defaults={
                'tags': tags,
                'count': 1,
            }
        )
        if not created:
            tc.incr('count')

        # XXX: We need some special handling for "data" as it shouldnt be part of the main hash??

        # TODO: this should be generated from the TypeProcessor
        ev_hash = 'foo'
        event = Event.objects.create(
            type=type,
            hash=ev_hash,
            date=date,
            time_spent=time_spent,
            tags=tags,
            **data
        )

        # TODO: this should be generated from the group's specified preindexes
        gr_hash = 'foo'
        group, created = Group.objects.get_or_create(
            type=type,
            hash=gr_hash + ev_hash,
            defaults={
                'count': 1,
                'time_spent': time_spent,
                'tags': tags,
            }
        )
        if not created:
            group.incr('count')
            if time_spent:
                group.incr('time_spent', time_spent)
        group.update(last_seen=event.date)

        group.add_relation(event, date.strftime('%s.%m'))

        # TODO: This logic should be some kind of "on-field-change" hook
        backend.add_to_index(Group, group.pk, 'last_seen', group.last_seen.strftime('%s.%m'))
        backend.add_to_index(Group, group.pk, 'time_spent', group.time_spent)
        backend.add_to_index(Group, group.pk, 'count', group.count)

        return group

    def process(self, **kwargs):
        from sentry.helpers import get_filters

        kwargs.setdefault('level', logging.ERROR)
        kwargs.setdefault('server_name', conf.NAME)

        if 'checksum' not in kwargs:
            checksum = construct_checksum(**kwargs)
        else:
            checksum = kwargs['checksum']

        # TODO: Cache should be handled by the db backend by default (as we expect a fast access backend)
        if conf.THRASHING_TIMEOUT and conf.THRASHING_LIMIT:
            cache_key = 'sentry:%s:%s' % (kwargs.get('class_name') or '', checksum)
            added = cache.add(cache_key, 1, conf.THRASHING_TIMEOUT)
            try:
                if not added and cache.incr(cache_key) > conf.THRASHING_LIMIT:
                    return
            except KeyError:
                pass

        for filter_ in get_filters():
            kwargs = filter_(None).process(kwargs) or kwargs

        # Make sure all additional data is coerced
        if 'data' in kwargs:
            kwargs['data'] = transform(kwargs['data'])

        return self.send(**kwargs)

    def send(self, **kwargs):
        if conf.REMOTE_URL:
            for url in conf.REMOTE_URL:
                data = {
                    'data': base64.b64encode(pickle.dumps(kwargs).encode('zlib')),
                    'key': conf.KEY,
                }
                try:
                    urlread(url, post=data, timeout=conf.REMOTE_TIMEOUT)
                except urllib2.URLError, e:
                    self.logger.error('Unable to reach Sentry log server: %s' % (e,), exc_info=sys.exc_info(), extra={'remote_url': url})
                    self.logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
                except urllib2.HTTPError, e:
                    self.logger.error('Unable to reach Sentry log server: %s' % (e,), exc_info=sys.exc_info(), extra={'body': e.read(), 'remote_url': url})
                    self.logger.log(kwargs.pop('level', None) or logging.ERROR, kwargs.pop('message', None))
        else:
            return self.create(**kwargs)

    def create_from_record(self, record, **kwargs):
        """
        Creates an error log for a `logging` module `record` instance.
        """
        for k in ('url', 'view', 'data'):
            if k not in kwargs:
                kwargs[k] = record.__dict__.get(k)

        request = getattr(record, 'request', None)
        if request:
            if not kwargs.get('data'):
                kwargs['data'] = {}
            kwargs['data'].update(dict(
                META=request.META,
                POST=request.POST,
                GET=request.GET,
                COOKIES=request.COOKIES,
            ))

            if not kwargs.get('url'):
                kwargs['url'] = request.build_absolute_uri()

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

    def create_from_text(self, message, **kwargs):
        """
        Creates an error log for from ``type`` and ``message``.
        """
        return self.process(
            message=message,
            **kwargs
        )

    def create_from_exception(self, exc_info=None, **kwargs):
        """
        Creates an error log from an exception.
        """
        if not exc_info:
            exc_info = sys.exc_info()

        exc_type, exc_value, exc_traceback = exc_info

        def shorten(var):
            var = transform(var)
            if isinstance(var, basestring) and len(var) > 200:
                var = var[:200] + '...'
            return var

        reporter = ExceptionReporter(None, exc_type, exc_value, exc_traceback)
        frames = varmap(shorten, reporter.get_traceback_frames())

        if not kwargs.get('view'):
            # This should be cached
            modules = get_installed_apps()
            if conf.INCLUDE_PATHS:
                modules = set(list(modules) + conf.INCLUDE_PATHS)

            def iter_tb_frames(tb):
                while tb:
                    yield tb.tb_frame
                    tb = tb.tb_next

            def contains(iterator, value):
                for k in iterator:
                    if value.startswith(k):
                        return True
                return False

            # We iterate through each frame looking for an app in INSTALLED_APPS
            # When one is found, we mark it as last "best guess" (best_guess) and then
            # check it against SENTRY_EXCLUDE_PATHS. If it isnt listed, then we
            # use this option. If nothing is found, we use the "best guess".
            best_guess = None
            view = None
            for frame in iter_tb_frames(exc_traceback):
                view = '.'.join([frame.f_globals['__name__'], frame.f_code.co_name])
                if contains(modules, view):
                    if not (contains(conf.EXCLUDE_PATHS, view) and best_guess):
                        best_guess = view
                elif best_guess:
                    break
            if best_guess:
                view = best_guess

            if view:
                kwargs['view'] = view

        data = kwargs.pop('data', {}) or {}
        data['__sentry__'] = {
            'exc': map(transform, [exc_type.__class__.__module__, exc_value.args, frames]),
        }

        if isinstance(exc_value, TemplateSyntaxError) and hasattr(exc_value, 'source'):
            origin, (start, end) = exc_value.source
            data['__sentry__'].update({
                'template': (origin.reload(), start, end, origin.name),
            })
            kwargs['view'] = origin.loadname

        tb_message = '\n'.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        kwargs.setdefault('message', transform(force_unicode(exc_value)))

        return self.process(
            class_name=exc_type.__name__,
            traceback=tb_message,
            data=data,
            **kwargs
        )

