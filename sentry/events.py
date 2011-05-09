import datetime
import hashlib
import re
import sys
import uuid

from flask import render_template

from sentry import app
from sentry.utils import get_versions, transform, shorten, varmap
from sentry.models import TagCount, Tag, Group, Event

def store(type, *args, **kwargs):
    proc = globals()[type]()
    data = {
        '__event__': proc.handle(*args, **kwargs),
    }
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

        event_message = self.to_string(event, data.get('__event__'))

        groups = []

        # For each view that handles this event, we need to create a Group
        for view in app.config['VIEWS'].itervalues():
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

                group.update(last_seen=event.date, score=group.get_score())

                group.add_relation(event, date.strftime('%s.%m'))

                groups.append(group)

        return event, groups

    def process(self, tags=[], date=None, time_spent=None, request=None, **data):
        "Processes the message before passing it on to the server"
        if request:
            data.update(dict(
                s_meta=request.META,
                s_post=request.POST,
                s_get=request.GET,
                s_cookies=request.COOKIES,
            ))
            tags.append(('url', request.build_absolute_uri()))

        tags.append(('server', app.config['NAME']))

        versions = get_versions()

        data['__sentry__'] = {}

        data['__sentry__']['versions'] = versions

        if data['__sentry__'].get('view'):
            # get list of modules from right to left
            parts = data['__sentry__']['view'].split('.')
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

        app.client.send(type=self.get_id(), tags=tags, data=data, date=date, time_spent=time_spent, event_id=event_id)

        return event_id

class MessageEvent(BaseEvent):
    """
    Messages store the following metadata:

    - msg_value: 'My message'
    """
    def get_event_hash(self, msg_value=None, **kwargs):
        return [msg_value]

    def to_string(self, event, data):
        return data['msg_value']

    def handle(self, message):
        return {
            'msg_value': message,
        }

class ExceptionEvent(BaseEvent):
    """
    Exceptions store the following metadata:

    - exc_value: 'My exception value'
    - exc_type: 'module.ClassName'
    - exc_frames: a list of serialized frames (see get_traceback_frames)
    - exc_template: 'template/name.html'
    """
    def get_event_hash(self, exc_value=None, exc_type=None, exc_frames=None, **kwargs):
        return [exc_value, exc_type]

    def to_string(self, event, data):
        return '%s: %s' % (data['exc_type'], data['exc_value'])

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
        # modules = get_installed_apps()
        modules = []
        if app.config['INCLUDE_PATHS']:
            modules = set(list(modules) + app.config['INCLUDE_PATHS'])

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
                if not (contains(app.config['EXCLUDE_PATHS'], view) and best_guess):
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

        result['exc_value'] = transform(exc_value)
        result['exc_type'] = exc_type
        result['exc_frames'] = self.get_traceback_frames(exc_traceback)

        return result

    def _get_lines_from_file(self, filename, lineno, context_lines, loader=None, module_name=None):
        """
        Returns context_lines before and after lineno from file.
        Returns (pre_context_lineno, pre_context, context_line, post_context).
        """
        source = None
        if loader is not None and hasattr(loader, "get_source"):
            source = loader.get_source(module_name)
            if source is not None:
                source = source.splitlines()
        if source is None:
            try:
                f = open(filename)
                try:
                    source = f.readlines()
                finally:
                    f.close()
            except (OSError, IOError):
                pass
        if source is None:
            return None, [], None, []

        encoding = 'ascii'
        for line in source[:2]:
            # File coding may be specified. Match pattern from PEP-263
            # (http://www.python.org/dev/peps/pep-0263/)
            match = re.search(r'coding[:=]\s*([-\w.]+)', line)
            if match:
                encoding = match.group(1)
                break
        source = [unicode(sline, encoding, 'replace') for sline in source]

        lower_bound = max(0, lineno - context_lines)
        upper_bound = lineno + context_lines

        pre_context = [line.strip('\n') for line in source[lower_bound:lineno]]
        context_line = source[lineno].strip('\n')
        post_context = [line.strip('\n') for line in source[lineno+1:upper_bound]]

        return lower_bound, pre_context, context_line, post_context

    def get_traceback_frames(self, tb):
        frames = []
        while tb is not None:
            # support for __traceback_hide__ which is used by a few libraries
            # to hide internal frames.
            if tb.tb_frame.f_locals.get('__traceback_hide__'):
                tb = tb.tb_next
                continue
            filename = tb.tb_frame.f_code.co_filename
            function = tb.tb_frame.f_code.co_name
            lineno = tb.tb_lineno - 1
            loader = tb.tb_frame.f_globals.get('__loader__')
            module_name = tb.tb_frame.f_globals.get('__name__')
            pre_context_lineno, pre_context, context_line, post_context = self._get_lines_from_file(filename, lineno, 7, loader, module_name)
            if pre_context_lineno is not None:
                frames.append({
                    'id': id(tb),
                    'filename': filename,
                    'module': module_name,
                    'function': function,
                    'lineno': lineno + 1,
                    # TODO: vars need to be references
                    'vars': tb.tb_frame.f_locals,
                    'pre_context': pre_context,
                    'context_line': context_line,
                    'post_context': post_context,
                    'pre_context_lineno': pre_context_lineno + 1,
                })
            tb = tb.tb_next
        return frames

    def to_html(self, event, data):
        return render_template('sentry/partial/events/exception.html', **{
            'exception_value': data['exc_value'],
            'exception_type': data['exc_type'],
            'frames': data['exc_frames'],
        })

class SQLEvent(BaseEvent):
    """
    Messages store the following metadata:

    - sql_value: 'SELECT * FROM table'
    - sql_engine: 'postgesql_psycopg2'
    """
    def get_event_hash(self, sql_value=None, sql_engine=None, **kwargs):
        return [sql_value, sql_engine]
