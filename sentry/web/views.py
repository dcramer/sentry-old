# TODO: this needs to be entirely flask

import base64
try:
    import cPickle as pickle
except ImportError:
    import pickle
import datetime
import logging
import re
import time
import warnings
import zlib

from flask import render_template, redirect, request, url_for, \
                  Module, current_app as app, abort, Response

from sentry.utils import get_filters, is_float, get_signature, parse_auth_header
from sentry.models import Group, Event
from sentry.plugins import GroupActionProvider
# from sentry.templatetags.sentry_helpers import with_priority
from sentry.web.reporter import ImprovedExceptionReporter

uuid_re = re.compile(r'^[a-z0-9]{32}$')

frontend = Module(__name__)

def login_required(func):
    def wrapped(request, *args, **kwargs):
        if not app.config['PUBLIC']:
            if not request.user.is_authenticated():
                return redirect(url_for('login'))
            if not request.user.has_perm('sentry.can_view'):
                return redirect(url_for('login'))
        return func(request, *args, **kwargs)
    wrapped.__doc__ = func.__doc__
    wrapped.__name__ = func.__name__
    return wrapped

@frontend.route('/auth/login/')
def login(request):
    # TODO:
    pass

@frontend.route('/auth/logout/')
def logout(request):
    # TODO:
    pass

@login_required
@frontend.route('/search/')
def search(request):
    try:
        page = int(request.args.get('p', 1))
    except (TypeError, ValueError):
        page = 1

    query = request.args.get('q')
    has_search = bool(app.config['SEARCH_ENGINE'])

    if query:
        if uuid_re.match(query):
            # Forward to message if it exists
            try:
                message = Message.objects.get(message_id=query)
            except Message.DoesNotExist:
                pass
            else:
                return redirect(message.get_absolute_url())
        elif not has_search:
            return render_template('sentry/invalid_message_id.html')
        else:
            message_list = get_search_query_set(query)
    else:
        message_list = GroupedMessage.objects.none()
    
    sort = request.args.get('sort')
    if sort == 'date':
        message_list = message_list.order_by('-last_seen')
    elif sort == 'new':
        message_list = message_list.order_by('-first_seen')
    else:
        sort = 'relevance'

    return render_template('sentry/search.html', {
        'message_list': message_list,
        'query': query,
        'sort': sort,
        'request': request,
    })

@login_required
@frontend.route('/')
def index():
    filters = []
    for filter_ in get_filters():
        filters.append(filter_(request))

    try:
        page = int(request.args.get('p', 1))
    except (TypeError, ValueError):
        page = 1

    query = request.args.get('content')
    is_search = query

    if is_search:
        if uuid_re.match(query):
            # Forward to message if it exists
            try:
                message = Event.objects.get(query)
            except Message.DoesNotExist:
                pass
            else:
                return redirect(message.get_absolute_url())
        message_list = self.get_search_query_set(query)
    else:
        message_list = Group.objects.all()

    sort = request.args.get('sort')
    # if sort == 'date':
    #     message_list = message_list.order_by('-last_seen')
    # elif sort == 'new':
    #     message_list = message_list.order_by('-first_seen')
    # else:
    #     sort = 'priority'
    #     if not is_search:
    #         message_list = message_list.order_by('-score', '-last_seen')

    filters = []

    any_filter = False
    # for filter_ in filters:
    #     if not filter_.is_set():
    #         continue
    #     any_filter = True
        # message_list = filter_.get_query_set(message_list)

    today = datetime.datetime.now()

    has_realtime = page == 1

    return render_template('sentry/index.html', **{
        'has_realtime': has_realtime,
        'message_list': message_list,
        'today': today,
        'query': query,
        'sort': sort,
        'any_filter': any_filter,
        'request': request,
        'filters': filters,
    })

@login_required
@frontend.route('/api/')
def ajax_handler():
    op = request.form.get('op')

    if op == 'poll':
        filters = []
        for filter_ in get_filters():
            filters.append(filter_(request))

        query = request.args.get('content')
        is_search = query

        if is_search:
            message_list = self.get_search_query_set(query)
        else:
            message_list = GroupedMessage.objects.extra(
                select={
                    'score': GroupedMessage.get_score_clause(),
                }
            )
            if query:
                # You really shouldnt be doing this
                message_list = message_list.filter(
                    Q(view__icontains=query) \
                    | Q(message__icontains=query) \
                    | Q(traceback__icontains=query)
                )

        sort = request.args.get('sort')
        if sort == 'date':
            message_list = message_list.order_by('-last_seen')
        elif sort == 'new':
            message_list = message_list.order_by('-first_seen')
        else:
            sort = 'priority'
            if not is_search:
                message_list = message_list.order_by('-score', '-last_seen')

        for filter_ in filters:
            if not filter_.is_set():
                continue
            message_list = filter_.get_query_set(message_list)

        data = [
            (m.pk, {
                'html': self.render_to_string('sentry/partial/_group.html', {
                    'group': m,
                    'priority': p,
                    'request': request,
                }, request),
                'count': m.times_seen,
                'priority': p,
            }) for m, p in with_priority(message_list[0:15])]

    elif op == 'resolve':
        gid = request.REQUEST.get('gid')
        if not gid:
            return HttpResponseForbidden()
        try:
            group = GroupedMessage.objects.get(pk=gid)
        except GroupedMessage.DoesNotExist:
            return HttpResponseForbidden()

        GroupedMessage.objects.filter(pk=group.pk).update(status=1)
        group.status = 1

        if not request.is_ajax():
            return redirect(request.environ['HTTP_REFERER'])

        data = [
            (m.pk, {
                'html': self.render_to_string('sentry/partial/_group.html', {
                    'group': m,
                    'request': request,
                }, request),
                'count': m.times_seen,
            }) for m in [group]]
    else:
        return HttpResponseBadRequest()

    response = HttpResponse(simplejson.dumps(data))
    response['Content-Type'] = 'application/json'
    return response

@login_required
@frontend.route('/event/<event_id>')
def group_details():
    group = get_object_or_404(GroupedMessage, pk=group_id)

    obj = group.message_set.all().order_by('-id')[0]
    if '__sentry__' in obj.data:
        module, args, frames = obj.data['__sentry__']['exc']
        obj.class_name = str(obj.class_name)
        # We fake the exception class due to many issues with imports/builtins/etc
        exc_type = type(obj.class_name, (Exception,), {})
        exc_value = exc_type(obj.message)

        exc_value.args = args

        reporter = ImprovedExceptionReporter(obj.request, exc_type, exc_value, frames, obj.data['__sentry__'].get('template'))
        traceback = mark_safe(reporter.get_traceback_html())
    elif group.traceback:
        traceback = mark_safe('<pre>%s</pre>' % (group.traceback,))

    def iter_data(obj):
        for k, v in obj.data.iteritems():
            if k.startswith('_') or k in ['url']:
                continue
            yield k, v

    return render_template('sentry/group/details.html', {
        'page': 'details',
        'group': group,
        'json_data': iter_data(obj),
        'traceback': traceback,
    }, request)

@login_required
@frontend.route('/event/<event_id>/messages/')
def group_message_list(self, request, group_id):
    group = get_object_or_404(GroupedMessage, pk=group_id)

    message_list = group.message_set.all().order_by('-datetime')

    page = 'messages'

    return render_template('sentry/group/message_list.html', {
        'page': 'messages',
        'group': group,
        'message_list': message_list,
    }, request)

@login_required
@frontend.route('/event/<event_id>/messages/<message_id>/')
def group_message_details():
    group = get_object_or_404(GroupedMessage, pk=group_id)

    message = get_object_or_404(group.message_set, pk=message_id)

    if '__sentry__' in message.data:
        module, args, frames = message.data['__sentry__']['exc']
        message.class_name = str(message.class_name)
        # We fake the exception class due to many issues with imports/builtins/etc
        exc_type = type(message.class_name, (Exception,), {})
        exc_value = exc_type(message.message)

        exc_value.args = args

        reporter = ImprovedExceptionReporter(message.request, exc_type, exc_value, frames, message.data['__sentry__'].get('template'))
        traceback = mark_safe(reporter.get_traceback_html())
    elif group.traceback:
        traceback = mark_safe('<pre>%s</pre>' % (group.traceback,))

    def iter_data(obj):
        for k, v in obj.data.iteritems():
            if k.startswith('_') or k in ['url']:
                continue
            yield k, v

    return render_template('sentry/group/message.html', {
        'page': 'messages',
        'json_data': iter_data(message),
        'group': group,
        'message': message,
        'traceback': traceback,
    }, request)

@frontend.route('/store/')
def store():
    if request.method != 'POST':
        return HttpResponseNotAllowed('This method only supports POST requests')

    if request.environ.get('AUTHORIZATION', '').startswith('Sentry'):
        auth_vars = parse_auth_header(request.META['AUTHORIZATION'])
        
        signature = auth_vars.get('sentry_signature')
        timestamp = auth_vars.get('sentry_timestamp')

        format = 'json'

        data = request.raw_post_data

        # Signed data packet
        if signature and timestamp:
            try:
                timestamp = float(timestamp)
            except ValueError:
                abort(400, 'Invalid Timestamp')

            if timestamp < time.time() - 3600: # 1 hour
                abort(410, 'Message has expired')

            sig_hmac = get_signature(data, timestamp)
            if sig_hmac != signature:
                return HttpResponseForbidden('Invalid signature')
        else:
            return HttpResponse('Unauthorized', status_code=401)
    else:
        data = request.form.get('data')
        if not data:
            return HttpResponseBadRequest('Missing data')

        format = request.form.get('format', 'pickle')

        if format not in ('pickle', 'json'):
            return HttpResponseBadRequest('Invalid format')

        # Legacy request (deprecated as of 2.0)
        key = request.form.get('key')
        
        if key != app.config['KEY']:
            warnings.warn('A client is sending the `key` parameter, which will be removed in Sentry 2.0', DeprecationWarning)
            return HttpResponseForbidden('Invalid credentials')

    logger = logging.getLogger('sentry.server')

    try:
        try:
            data = base64.b64decode(data).decode('zlib')
        except zlib.error:
            data = base64.b64decode(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        return HttpResponseForbidden('Bad data decoding request (%s, %s)' % (e.__class__.__name__, e))

    try:
        if format == 'pickle':
            data = pickle.loads(data)
        elif format == 'json':
            data = simplejson.loads(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        return HttpResponseForbidden('Bad data reconstructing object (%s, %s)' % (e.__class__.__name__, e))

    # XXX: ensure keys are coerced to strings
    data = dict((smart_str(k), v) for k, v in data.iteritems())

    if 'timestamp' in data:
        if is_float(data['timestamp']):
            data['timestamp'] = datetime.datetime.fromtimestamp(float(data['timestamp']))
        else:
            if '.' in data['timestamp']:
                format = '%Y-%m-%dT%H:%M:%S.%f'
            else:
                format = '%Y-%m-%dT%H:%M:%S'
            data['timestamp'] = datetime.datetime.strptime(data['timestamp'], format)

    GroupedMessage.objects.from_kwargs(**data)
    
    return HttpResponse()

@login_required
def group_plugin_action(request, group_id, slug):
    group = get_object_or_404(GroupedMessage, pk=group_id)
    
    try:
        cls = GroupActionProvider.plugins[slug]
    except KeyError:
        raise Http404('Plugin not found')
    response = cls(group_id)(request, group)
    if response:
        return response
    return redirect(request.META.get('HTTP_REFERER') or reverse('sentry'))

@frontend.route('/_static/<path:path>', strict_slashes=False)
def static_media(path):
    """
    Serve static files below a given point in the directory structure.
    """
    from django.utils.http import http_date
    from django.views.static import was_modified_since
    import mimetypes
    import os.path
    import posixpath
    import stat
    import urllib

    document_root = os.path.join(app.config['ROOT'], 'static')
    
    path = posixpath.normpath(urllib.unquote(path))
    path = path.lstrip('/')
    newpath = ''
    for part in path.split('/'):
        if not part:
            # Strip empty path components.
            continue
        drive, part = os.path.splitdrive(part)
        head, part = os.path.split(part)
        if part in (os.curdir, os.pardir):
            # Strip '.' and '..' in path.
            continue
        newpath = os.path.join(newpath, part).replace('\\', '/')
    if newpath and path != newpath:
        return redirect(newpath)
    fullpath = os.path.join(document_root, newpath)
    print fullpath
    if os.path.isdir(fullpath):
        abort(404, "Directory indexes are not allowed here.")
    if not os.path.exists(fullpath):
        abort(404, '"%s" does not exist' % fullpath)
    # Respect the If-Modified-Since header.
    statobj = os.stat(fullpath)
    mimetype = mimetypes.guess_type(fullpath)[0] or 'application/octet-stream'
    if not was_modified_since(request.environ.get('HTTP_IF_MODIFIED_SINCE'),
                              statobj[stat.ST_MTIME], statobj[stat.ST_SIZE]):
        abort(304, mimetype=mimetype)
    contents = open(fullpath, 'rb').read()
    return Response(contents, mimetype=mimetype, headers=(
        ('Last-Modified', http_date(statobj[stat.ST_MTIME])),
        ('Content-Length', len(contents)),
    ))
