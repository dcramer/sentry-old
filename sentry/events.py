import datetime
import hashlib
import sys
import traceback
import uuid

from sentry import conf
from sentry.client import client
from sentry.helpers import get_versions, transform, shorten, varmap, get_installed_apps
from sentry.models import TagCount, Tag, Group, Event

def store(type, *args, **kwargs):
    proc = globals()[type]()
    data = proc.handle(*args, **kwargs)
    result = proc.process(**data)
    return result

class BaseEvent(object):
    def get_id(self):
        "Returns a unique identifier for this event class."
        return '.'.join([self.__class__.__module__, self.__class__.__name__])

    def store(self, tags=[], data={}, date=None, time_spent=None, event_id=None):
        "Saves the event in the database."
        proc_id = self.get_id()

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

        # XXX: We need some special handling for "data" as it shouldnt be part of the main hash??

        # TODO: this should be generated from the TypeProcessor
        event_hash = hashlib.md5('|'.join(k or '' for k in self.get_event_hash(**data))).hexdigest()

        event = Event.objects.create(
            pk=event_id,
            type=proc_id,
            hash=event_hash,
            date=date,
            time_spent=time_spent,
            tags=tags,
        )
        event.set_meta(**data)

        event_message = self.to_string(event)

        groups = []

        # For each view that handles this event, we need to create a Group
        for view in conf.VIEWS.itervalues():
            if view['event'] == proc_id:
                # We only care about tags which are required for this view

                event_tags = [(k, v) for k, v in tags if k in view.get('tags', [])]
                tags_hash = TagCount.get_tags_hash(event_tags)

                # Handle TagCount creation and incrementing
                tc, created = TagCount.objects.get_or_create(
                    hash=tags_hash,
                    defaults={
                        'tags': tags,
                        'count': 1,
                    }
                )
                if not created:
                    tc.incr('count')

                group, created = Group.objects.get_or_create(
                    type=proc_id,
                    hash=tags_hash + event_hash,
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
                group.update(last_seen=event.date)

                group.add_relation(event, date.strftime('%s.%m'))

                groups.append(group)

        return event, groups

    def process(self, tags=[], date=None, time_spent=None, request=None, **data):
        "Processes the message before passing it on to the server"
        from sentry.helpers import get_filters

        if request:
            data.update(dict(
                s_meta=request.META,
                s_post=request.POST,
                s_get=request.GET,
                s_cookies=request.COOKIES,
            ))
            tags.append(('url', request.build_absolute_uri()))

        tags.append(('server', conf.NAME))

        versions = get_versions()

        data['s_versions'] = versions

        if data.get('s_view'):
            # get list of modules from right to left
            parts = data['s_view'].split('.')
            module_list = ['.'.join(parts[:idx]) for idx in xrange(1, len(parts)+1)][::-1]
            version = None
            module = None
            for m in module_list:
                if m in versions:
                    module = m
                    version = versions[m]

            data['s_view'] = view

            # store our "best guess" for application version
            if version:
                data.update({
                    's_version': version,
                    's_module': module,
                })

        # TODO: Cache should be handled by the db backend by default (as we expect a fast access backend)
        # if conf.THRASHING_TIMEOUT and conf.THRASHING_LIMIT:
        #     cache_key = 'sentry:%s:%s' % (kwargs.get('class_name') or '', checksum)
        #     added = cache.add(cache_key, 1, conf.THRASHING_TIMEOUT)
        #     if not added:
        #         try:
        #             thrash_count = cache.incr(cache_key)
        #         except (KeyError, ValueError):
        #             # cache.incr can fail. Assume we aren't thrashing yet, and
        #             # if we are, hope that the next error has a successful
        #             # cache.incr call.
        #             thrash_count = 0
        #         if thrash_count > conf.THRASHING_LIMIT:
        #             return

        # for filter_ in get_filters():
        #     kwargs = filter_(None).process(kwargs) or kwargs

        # create ID client-side so that it can be passed to application
        event_id = uuid.uuid4().hex

        # Make sure all data is coerced
        data = transform(data)

        client.send(type=self.get_id(), tags=tags, data=data, date=date, time_spent=time_spent, event_id=event_id)

        return event_id

class MessageEvent(BaseEvent):
    """
    Messages store the following metadata:

    - msg_value: 'My message'
    """
    def get_event_hash(self, msg_value=None, **kwargs):
        return [msg_value]

    def to_string(self, event):
        return event.data['msg_value']

    def handle(self, message):
        return {
            'msg_value': message,
        }

class ExceptionEvent(BaseEvent):
    """
    Exceptions store the following metadata:

    - exc_value: 'My exception value'
    - exc_type: 'module.ClassName'
    - exc_frames: [(module path, line number, line text, truncated locals)]
    - exc_template: 'template/name.html'
    """
    def get_event_hash(self, exc_value=None, exc_type=None, exc_frames=None, **kwargs):
        return [exc_value, exc_type]

    def to_string(self, event):
        return '%s: %s' % (event.data['exc_type'], event.data['exc_value'])

    def handle(self, exc_info=None):
        # TODO: remove Django specifics
        from django.template import TemplateSyntaxError
        from django.views.debug import ExceptionReporter

        if exc_info is None:
            exc_info = sys.exc_info()

        exc_type, exc_value, exc_traceback = exc_info

        result = {
            'tags': [('level', 'error')],
        }

        reporter = ExceptionReporter(None, exc_type, exc_value, exc_traceback)
        exc_frames = varmap(shorten, reporter.get_traceback_frames())

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
            try:
                view = '.'.join([frame.f_globals['__name__'], frame.f_code.co_name])
            except:
                continue
            if contains(modules, view):
                if not (contains(conf.EXCLUDE_PATHS, view) and best_guess):
                    best_guess = view
            elif best_guess:
                break
        if best_guess:
            view = best_guess

        if view:
            result['tags'].append(('view', view))

        if hasattr(exc_type, '__class__'):
            exc_module = exc_type.__class__.__module__
            if exc_module == '__builtin__':
                exc_type = exc_type.__name__
            else:
                exc_type = '%s.%s' % (exc_module, exc_type.__name__)
        else:
            exc_module = None
            exc_type = exc_type.__name__

        if isinstance(exc_value, TemplateSyntaxError) and hasattr(exc_value, 'source'):
            origin, (start, end) = exc_value.source
            result['exc_template'] = (origin.reload(), start, end, origin.name)
            result['tags'].append(('template', origin.loadname))

        tb_message = '\n'.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        result['exc_value'] = transform(exc_value)
        result['exc_type'] = exc_type

        return result

class SQLEvent(BaseEvent):
    """
    Messages store the following metadata:

    - sql_value: 'SELECT * FROM table'
    - sql_engine: 'postgesql_psycopg2'
    """
    def get_event_hash(self, sql_value=None, sql_engine=None, **kwargs):
        return [sql_value, sql_engine]