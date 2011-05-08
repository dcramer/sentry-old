# Widget api is pretty ugly
from __future__ import absolute_import

from collections import OrderedDict
from flask import current_app as app
from jinja2 import Markup, escape

class Widget(object):
    def __init__(self, filter, request):
        self.filter = filter
        self.request = request

    def get_query_string(self):
        return self.filter.get_query_string()

class TextWidget(Widget):
    def render(self, value, placeholder='', **kwargs):
        return Markup('<div class="filter-text"><p class="textfield"><input type="text" name="%(name)s" value="%(value)s" placeholder="%(placeholder)s"/></p><p class="submit"><input type="submit" class="search-submit"/></p></div>' % dict(
            name=self.filter.get_query_param(),
            value=escape(value),
            placeholder=escape(placeholder or 'enter %s' % self.filter.label.lower()),
        ))

class ChoiceWidget(Widget):
    def render(self, value, **kwargs):
        choices = self.filter.get_choices()
        query_string = self.get_query_string()
        column = self.filter.get_query_param()

        output = ['<ul class="%s-list filter-list" rel="%s">' % (self.filter.column, column)]
        output.append('<li%(active)s><a href="%(query_string)s&amp;%(column)s=">Any %(label)s</a></li>' % dict(
            active=not value and ' class="active"' or '',
            query_string=query_string,
            label=self.filter.label,
            column=column,
        ))
        for key, val in choices.iteritems():
            key = unicode(key)
            output.append('<li%(active)s rel="%(key)s"><a href="%(query_string)s&amp;%(column)s=%(key)s">%(value)s</a></li>' % dict(
                active=value == key and ' class="active"' or '',
                column=column,
                key=key,
                value=val,
                query_string=query_string,
            ))
        output.append('</ul>')
        return Markup('\n'.join(output))

class SentryFilter(object):
    label = ''
    column = ''
    widget = ChoiceWidget
    # This must be a string
    default = ''
    show_label = True
    
    def __init__(self, request):
        self.request = request
    
    def is_set(self):
        return bool(self.get_value())
    
    def get_value(self):
        return self.request.GET.get(self.get_query_param(), self.default) or ''
    
    def get_query_param(self):
        return getattr(self, 'query_param', self.column)

    def get_widget(self):
        return self.widget(self, self.request)
    
    def get_query_string(self):
        column = self.column
        query_dict = self.request.GET.copy()
        if 'p' in query_dict:
            del query_dict['p']
        if column in query_dict:
            del query_dict[self.column]
        return '?' + query_dict.urlencode()
    
    def get_choices(self):
        from sentry.models import FilterValue
        return OrderedDict((l, l) for l in FilterValue.objects.filter(key=self.column)\
                                                     .values_list('value', flat=True)\
                                                     .order_by('value'))
    
    def get_query_set(self, queryset):
        from sentry.models import MessageIndex
        kwargs = {self.column: self.get_value()}
        if self.column.startswith('data__'):
            return MessageIndex.objects.get_for_queryset(queryset, **kwargs)
        return queryset.filter(**kwargs)
    
    def process(self, data):
        """``self.request`` is not available within this method"""
        return data
    
    def render(self):
        widget = self.get_widget()
        return widget.render(self.get_value())

class StatusFilter(SentryFilter):
    label = 'Status'
    column = 'status'
    default = '0'

    def get_choices(self):
        return OrderedDict([
            (0, 'Unresolved'),
            (1, 'Resolved'),
        ])

class LoggerFilter(SentryFilter):
    label = 'Logger'
    column = 'logger'

class ServerNameFilter(SentryFilter):
    label = 'Server Name'
    column = 'server_name'

    def get_query_set(self, queryset):
        return queryset.filter(message_set__server_name=self.get_value()).distinct()

class SiteFilter(SentryFilter):
    label = 'Site'
    column = 'site'

    def process(self, data):
        if 'site' in data:
            return data
        if app.config['SITE']:
            data['site'] = app.config['SITE']
        return data

    def get_query_set(self, queryset):
        return queryset.filter(message_set__site=self.get_value()).distinct()

class LevelFilter(SentryFilter):
    label = 'Level'
    column = 'level'
    
    def get_choices(self):
        return OrderedDict((str(k), v) for k, v in app.config['LOG_LEVELS'])
    
    def get_query_set(self, queryset):
        return queryset.filter(level__gte=self.get_value())