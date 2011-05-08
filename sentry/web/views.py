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

from jinja2 import Markup
from flask import render_template, redirect, request, url_for, \
                  abort, Response

from sentry import app
from sentry.utils import get_filters, is_float, get_signature, parse_auth_header
from sentry.utils.shortcuts import get_object_or_404
from sentry.models import Group, Event
from sentry.plugins import GroupActionProvider
# from sentry.templatetags.sentry_helpers import with_priority
from sentry.web.reporter import ImprovedExceptionReporter

uuid_re = re.compile(r'^[a-z0-9]{32}$')

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

@app.route('/auth/login/')
def login(request):
    # TODO:
    pass

@app.route('/auth/logout/')
def logout(request):
    # TODO:
    pass

@login_required
@app.route('/search/')
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
        message_list = Group.objects.none()
    
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
@app.route('/')
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
@app.route('/api/')
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
            abort(403)
        try:
            group = GroupedMessage.objects.get(pk=gid)
        except GroupedMessage.DoesNotExist:
            abort(403)

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
        abort(400)

    return Response(simplejson.dumps(data), mimetype='application/json')

@login_required
@app.route('/group/<group_id>')
def group_details(group_id):
    group = get_object_or_404(Group, pk=group_id)
    
    last_event = group.get_relations(Event, limit=1)[0]

    def iter_data(obj):
        for k, v in obj.data.iteritems():
            if k.startswith('_') or k in ['url']:
                continue
            yield k, v

    # Render our event's custom output
    event_html = Markup(last_event.get_processor().to_html(last_event))
    
    return render_template('sentry/group/details.html', **{
        'page': 'details',
        'group': group,
        'json_data': iter_data(last_event),
        'event_html': event_html,
    })

@login_required
@app.route('/group/<group_id>/messages/')
def group_message_list(group_id):
    group = get_object_or_404(GroupedMessage, pk=group_id)

    message_list = group.message_set.all().order_by('-datetime')

    page = 'messages'

    return render_template('sentry/group/message_list.html', **{
        'page': 'messages',
        'group': group,
        'message_list': message_list,
    })

@login_required
@app.route('/group/<group_id>/events/<event_id>/')
def group_message_details(group_id, event_id):
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

    return render_template('sentry/group/message.html', **{
        'page': 'messages',
        'json_data': iter_data(message),
        'group': group,
        'message': message,
        'traceback': traceback,
    })

@app.route('/store/', methods=['POST'])
def store():
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
                abort(403, 'Invalid signature')
        else:
            abort(401,'Unauthorized')
    else:
        data = request.form.get('data')
        if not data:
            abort(400, 'Missing data')

        format = request.form.get('format', 'pickle')

        if format not in ('pickle', 'json'):
            abort(400, 'Invalid format')

        # Legacy request (deprecated as of 2.0)
        key = request.form.get('key')
        
        if key != app.config['KEY']:
            warnings.warn('A client is sending the `key` parameter, which will be removed in Sentry 2.0', DeprecationWarning)
            abort(403, 'Invalid credentials')

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
        abort(400, 'Bad data decoding request (%s, %s)' % (e.__class__.__name__, e))

    try:
        if format == 'pickle':
            data = pickle.loads(data)
        elif format == 'json':
            data = simplejson.loads(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        abort(403, 'Bad data reconstructing object (%s, %s)' % (e.__class__.__name__, e))

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
    
    return ''

@login_required
def group_plugin_action(request, group_id, slug):
    group = get_object_or_404(GroupedMessage, pk=group_id)
    
    try:
        cls = GroupActionProvider.plugins[slug]
    except KeyError:
        abort(404, 'Plugin not found')
    response = cls(group_id)(request, group)
    if response:
        return response
    return redirect(request.META.get('HTTP_REFERER') or reverse('sentry'))
