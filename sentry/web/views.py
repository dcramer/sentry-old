"""
sentry.web.views
~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

# TODO: this needs to be entirely flask

import datetime
import re
import simplejson

from jinja2 import Markup
from flask import render_template, redirect, request, url_for, \
                  abort, Response

from sentry import app
from sentry.core.plugins import GroupActionProvider
from sentry.models import Group, Event, EventType
from sentry.web import filters
from sentry.web.templatetags import with_priority
from sentry.utils.shortcuts import get_object_or_404

uuid_re = re.compile(r'^[a-z0-9]{32}$')

def login_required(func):
    def wrapped(*args, **kwargs):
        # TODO: auth
        # if not app.config['PUBLIC']:
        #     if not request.user.is_authenticated():
        #         return redirect(url_for('login'))
        #     if not request.user.has_perm('sentry.can_view'):
        #         return redirect(url_for('login'))
        return func(request, *args, **kwargs)
    wrapped.__doc__ = func.__doc__
    wrapped.__name__ = func.__name__
    wrapped.__wraps__ = getattr(func, '__wraps__', func)
    return wrapped

@app.errorhandler(404)
def page_not_found(e):
    return render_template('sentry/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('sentry/500.html'), 500

@app.context_processor
def context():
    return {
        'event_type_list': EventType.objects.all(),
    }

@app.route('/auth/login/')
def login():
    # TODO:
    pass

@app.route('/auth/logout/')
def logout():
    # TODO:
    pass

@login_required
@app.route('/search/')
def search():
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
                event = Event.objects.get(query)
            except Event.DoesNotExist:
                pass
            else:
                return redirect(event.get_absolute_url())
        elif not has_search:
            return render_template('sentry/invalid_message_id.html')
        else:
            # TODO:
            # event_list = get_search_query_set(query)
            raise NotImplementedError
    else:
        event_list = Group.objects.none()
    
    sort = request.args.get('sort')
    if sort == 'date':
        event_list = event_list.order_by('-last_seen')
    elif sort == 'new':
        event_list = event_list.order_by('-first_seen')
    else:
        sort = 'relevance'

    return render_template('sentry/search.html', **{
        'event_list': event_list,
        'query': query,
        'sort': sort,
        'request': request,
        'page': page,
    })

@login_required
@app.route('/')
def index():
    filter_list = list(filters.all())

    try:
        page = int(request.args.get('p', 1))
    except (TypeError, ValueError):
        page = 1

    event_list = Group.objects.all()

    sort = request.args.get('sort')
    if sort == 'date':
        event_list = event_list.order_by('-last_seen')
    elif sort == 'new':
        event_list = event_list.order_by('-first_seen')
    elif sort == 'count':
        event_list = event_list.order_by('-count')
    else:
        sort = 'priority'
        event_list = event_list.order_by('-score')

    any_filter = False
    # for filter_ in filters:
    #     if not filter_.is_set():
    #         continue
    #     any_filter = True
        # event_list = filter_.get_query_set(event_list)

    today = datetime.datetime.now()

    has_realtime = page == 1
    
    return render_template('sentry/index.html', **{
        'has_realtime': has_realtime,
        'event_list': event_list,
        'today': today,
        'sort': sort,
        'any_filter': any_filter,
        'request': request,
        'filter_list': filter_list,
    })

@login_required
@app.route('/api/')
def ajax_handler():
    op = request.form.get('op')

    if op == 'poll':
        filters = []
        for filter_ in filters.all():
            filters.append(filter_(request))

        event_list = Group.objects

        sort = request.args.get('sort')
        if sort == 'date':
            event_list = event_list.order_by('-last_seen')
        elif sort == 'new':
            event_list = event_list.order_by('-first_seen')
        elif sort == 'count':
            event_list = event_list.order_by('-count')
        else:
            sort = 'priority'
            event_list = event_list.order_by('-score')

        # for filter_ in filters:
        #     if not filter_.is_set():
        #         continue
        #     event_list = filter_.get_query_set(event_list)

        data = [
            (m.pk, {
                'html': render_template('sentry/partial/group.html', **{
                    'group': m,
                    'priority': p,
                    'request': request,
                }),
                'count': m.times_seen,
                'priority': p,
            }) for m, p in with_priority(event_list[0:15])]

    elif op == 'resolve':
        gid = request.REQUEST.get('gid')
        if not gid:
            abort(403)
        try:
            group = Group.objects.get(pk=gid)
        except Group.DoesNotExist:
            abort(403)

        group.update(status=1)

        if not request.is_ajax():
            return redirect(request.environ['HTTP_REFERER'])

        data = [
            (m.pk, {
                'html': render_template('sentry/partial/group.html', **{
                    'group': m,
                    'request': request,
                }),
                'count': m.times_seen,
            }) for m in [group]]
    else:
        abort(400)

    return Response(simplejson.dumps(data), mimetype='application/json')

@login_required
@app.route('/group/<group_id>/')
def group_details(group_id):
    group = get_object_or_404(Group, pk=group_id)
    
    last_event = group.get_relations(Event, limit=1)[0]

    def iter_data(obj):
        for k, v in obj.data.get('extra', {}).iteritems():
            if k.startswith('_') or k in ['url']:
                continue
            yield k, v

    return render_template('sentry/group/details.html', **{
        'page': 'details',
        'interface_list': filter(None, [Markup(i.to_html(last_event) or '') for i in last_event.get_interfaces()]),
        'group': group,
        'json_data': iter_data(last_event),
    })

@login_required
@app.route('/group/<group_id>/events/')
def group_event_list(group_id):
    group = get_object_or_404(Group, pk=group_id)

    event_list = group.get_relations(Event)

    return render_template('sentry/group/event_list.html', **{
        'page': 'events',
        'group': group,
        'event_list': event_list,
    })

@login_required
@app.route('/group/<group_id>/events/<event_id>/')
def group_event_details(group_id, event_id):
    group = get_object_or_404(Group, pk=group_id)
    event = get_object_or_404(Event, pk=event_id)

    def iter_data(obj):
        for k, v in obj.data['extra'].iteritems():
            if k.startswith('_') or k in ['url']:
                continue
            yield k, v

    return render_template('sentry/group/event.html', **{
        'page': 'events',
        'json_data': iter_data(event),
        'group': group,
        'event': event,
        'interface_list': filter(None, [Markup(i.to_html(event) or '') for i in event.get_interfaces()]),
    })

@login_required
@app.route('/group/<group_id>/<path:slug>')
def group_plugin_action(group_id, slug):
    group = get_object_or_404(Group, pk=group_id)
    
    try:
        cls = GroupActionProvider.plugins[slug]
    except KeyError:
        abort(404, 'Plugin not found')
    response = cls(group_id)(request, group)
    if response:
        return response
    return redirect(request.environ.get('HTTP_REFERER') or url_for('index'))
