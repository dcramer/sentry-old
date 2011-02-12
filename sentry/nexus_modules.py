import logging
import datetime
import nexus
import re
import zlib

from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.utils.safestring import mark_safe

from sentry import conf
from sentry.helpers import get_filters
from sentry.models import Event, Group
from sentry.plugins import GroupActionProvider
from sentry.templatetags.sentry_helpers import with_priority
from sentry.reporter import ImprovedExceptionReporter

from nexus.modules import NexusModule
from sentry.feeds import MessageFeed, SummaryFeed

uuid_re = re.compile(r'^[a-z0-9]{32}$')

class SentryNexusModule(NexusModule):
    home_url = 'index'

    def get_title(self):
        return 'Sentry'

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url

        return patterns('',
            # Feeds

            url(r'^feeds/%s/messages.xml$' % re.escape(conf.KEY), MessageFeed(), name='feed-messages'),
            url(r'^feeds/%s/summaries.xml$' % re.escape(conf.KEY), SummaryFeed(), name='feed-summaries'),

            # JS and API

            url(r'^jsapi/$', self.as_view(self.ajax_handler), name='ajax'),
            url(r'^store/$', self.store, name='store'),

            # Normal views

            url(r'^group/([a-zA-Z0-9]{32})$', self.as_view(self.group), name='group'),
            url(r'^group/([a-zA-Z0-9]{32})/messages$', self.as_view(self.group_message_list), name='group-messages'),
            url(r'^group/([a-zA-Z0-9]{32})/messages/([a-zA-Z0-9]{32})$', self.as_view(self.group_message_details), name='group-message'),
            url(r'^group/([a-zA-Z0-9]{32})/actions/([\w_-]+)', self.as_view(self.group_plugin_action), name='group-plugin-action'),

            url(r'^$', self.as_view(self.index), name='index'),
        )

    def get_search_query_set(self, query):
        from haystack.query import SearchQuerySet
        from sentry.search_indexes import site, backend

        class SentrySearchQuerySet(SearchQuerySet):
            "Returns actual instances rather than search results."

            def __getitem__(self, k):
                result = []
                for r in super(SentrySearchQuerySet, self).__getitem__(k):
                    r.object.score = r.score
                    result.append(r.object)
                return result

        return SentrySearchQuerySet(
            site=site,
            query=backend.SearchQuery(backend=site.backend),
        ).filter(content=query)

    # Views

    def index(self, request):
        filters = []
        for filter_ in get_filters():
            filters.append(filter_(request))

        try:
            page = int(request.GET.get('p', 1))
        except (TypeError, ValueError):
            page = 1

        query = request.GET.get('content')
        is_search = query

        if is_search:
            if uuid_re.match(query):
                # Forward to message if it exists
                try:
                    message = Event.objects.get(query)
                except Message.DoesNotExist:
                    pass
                else:
                    return HttpResponseRedirect(message.get_absolute_url())
            message_list = self.get_search_query_set(query)
        else:
            message_list = Group.objects.all()

        sort = request.GET.get('sort')
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

        return self.render_to_response('sentry/index.html', {
            'has_realtime': has_realtime,
            'message_list': message_list,
            'today': today,
            'query': query,
            'sort': sort,
            'any_filter': any_filter,
            'request': request,
            'filters': filters,
        }, request)

    def ajax_handler(self, request):
        op = request.REQUEST.get('op')

        if op == 'poll':
            filters = []
            for filter_ in get_filters():
                filters.append(filter_(request))

            query = request.GET.get('content')
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

            sort = request.GET.get('sort')
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
                return HttpResponseRedirect(request.META['HTTP_REFERER'])

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

    def group(self, request, group_id):
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

        return self.render_to_response('sentry/group/details.html', {
            'page': 'details',
            'group': group,
            'json_data': iter_data(obj),
            'traceback': traceback,
        }, request)

    def group_message_list(self, request, group_id):
        group = get_object_or_404(GroupedMessage, pk=group_id)

        message_list = group.message_set.all().order_by('-datetime')

        page = 'messages'

        return self.render_to_response('sentry/group/message_list.html', {
            'page': 'messages',
            'group': group,
            'message_list': message_list,
        }, request)

    def group_message_details(self, request, group_id, message_id):
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

        return self.render_to_response('sentry/group/message.html', {
            'page': 'messages',
            'json_data': iter_data(message),
            'group': group,
            'message': message,
            'traceback': traceback,
        }, request)

    def store(self, request):
        """
        TODO: this isnt going to play nice with binary gzip data
        TODO: this should actually be part of some generic Nexus API solution
        
        API method to store a new event. All values must be specified as a ``data``
        parameter, which must be sent as a JSON hash. The ``data`` parameter may
        optionally be gzipped.
        
        The value of ``SENTRY_KEY`` must be sent as ``key``.

        The following keys are required:
        
        - type:
           - path.to.event.handler
        
        The following keys are optional:
        
        - date (default: now)
        - time_spent (default: 0)
        - tags (list):
          - (key, value)
        - data (dict):
          - key: value
        - event_id: (default: uuid4())
        """
        
        key = request.POST.get('key')
        if key != conf.KEY:
            return HttpResponseForbidden('Invalid credentials')

        data = request.POST.get('data')
        if not data:
            return HttpResponseForbidden('Missing data')
        if not data.startswith('{'):
            try:
                data = data.decode('zlib')
            except zlib.error:
                logger = logging.getLogger('sentry.server')
                # This error should be caught as it suggests that there's a
                # bug somewhere in the Sentry code.
                logger.exception('Bad data received')
                return HttpResponseForbidden('Data must be either gzipped or sent as raw JSON.')

        if 'type' not in data:
            return HttpResponseForbidden('Missing required attribute in data: type')

        store(data.pop('type'), data)

        return HttpResponse()

    def group_plugin_action(self, request, group_id, slug):
        group = get_object_or_404(GroupedMessage, pk=group_id)

        try:
            cls = GroupActionProvider.plugins[slug]
        except KeyError:
            raise Http404('Plugin not found')
        response = cls(group_id)(request, group)
        if response:
            return response
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
nexus.site.register(SentryNexusModule, 'sentry')