# Widget api is pretty ugly
from __future__ import absolute_import

from sentry import app
from sentry.models import Tag
from flask import request
from jinja2 import Markup, escape

class Widget(object):
    def __init__(self, filter):
        self.filter = filter

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
        for key, val in choices:
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

class Filter(object):
    label = ''
    column = ''
    widget = None
    # This must be a string
    default = ''
    show_label = True
    
    def is_set(self):
        return bool(self.get_value())
    
    def get_value(self):
        return request.args.get(self.get_query_param(), self.default) or ''
    
    def get_query_param(self):
        return getattr(self, 'query_param', self.column)

    def get_widget(self):
        return self.widget(self)
    
    def get_query_string(self):
        column = self.column
        query_dict = request.args.copy()
        if 'p' in query_dict:
            del query_dict['p']
        if column in query_dict:
            del query_dict[self.column]
        return ''
        # TODO: urlencode doesnt exist on Flask request dicts
        return '?' + query_dict.urlencode()
    
    def get_choices(self):
        return [(t.value, t.value) for t in Tag.objects.filter(key=self.column)]
    
    def get_query_set(self, queryset):
        from sentry.models import MessageIndex
        kwargs = {self.column: self.get_value()}
        if self.column.startswith('data__'):
            return MessageIndex.objects.get_for_queryset(queryset, **kwargs)
        return queryset.filter(**kwargs)
    
    def process(self, data):
        return data
    
    def render(self):
        widget = self.get_widget()
        return widget.render(self.get_value())

class Choice(Filter):
    widget = ChoiceWidget
    
    def __init__(self, tag):
        self.tag = tag
        self.label = tag.title()
