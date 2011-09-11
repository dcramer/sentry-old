"""
sentry.web.filters
~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

# Widget api is pretty ugly
from __future__ import absolute_import

import logging

from flask import request
from jinja2 import Markup, escape
from sentry import app
from sentry.models import Tag

_CACHE = None
def all(from_cache=True):
    global _CACHE

    if _CACHE is None or not from_cache:
        modules = []
        for key, path in app.config['FILTERS']:
            module_name, class_name = path.rsplit('.', 1)
            try:
                module = __import__(module_name, {}, {}, class_name)
                handler = getattr(module, class_name)
            except Exception:
                logger = logging.getLogger(__name__)
                logger.exception('Unable to import %s' % (path,))
                continue
            modules.append(handler(key))

        _CACHE = modules

    for f in _CACHE:
        yield f

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
        tag = self.filter.get_query_param()

        output = ['<ul class="filter-list" rel="%s">' % (tag,)]
        output.append('<li%(active)s><a href="%(query_string)s&amp;%(tag)s=">Any %(label)s</a></li>' % dict(
            active=not value and ' class="active"' or '',
            query_string=query_string,
            label=self.filter.label,
            tag=tag,
        ))
        for key, val in choices:
            key = unicode(key)
            output.append('<li%(active)s rel="%(key)s"><a href="%(query_string)s&amp;%(tag)s=%(key)s">%(value)s</a></li>' % dict(
                active=value == key and ' class="active"' or '',
                tag=tag,
                key=key,
                value=val,
                query_string=query_string,
            ))
        output.append('</ul>')
        return Markup('\n'.join(output))

class Filter(object):
    label = ''
    widget = None
    # This must be a string
    default = ''
    show_label = True
    
    def __init__(self, tag):
        self.tag = tag
        self.label = tag.title()
    
    def is_set(self):
        return bool(self.get_value())
    
    def get_value(self):
        return request.args.get(self.get_query_param(), self.default) or ''
    
    def get_query_param(self):
        return getattr(self, 'query_param', self.tag)

    def get_widget(self):
        return self.widget(self)
    
    def get_query_string(self):
        tag = self.tag
        query_dict = request.args.copy()
        if 'p' in query_dict:
            del query_dict['p']
        if tag in query_dict:
            del query_dict[self.tag]
        return ''
        # TODO: urlencode doesnt exist on Flask request dicts
        return '?' + query_dict.urlencode()
    
    def get_choices(self):
        return [(t.value, t.value) for t in Tag.objects.filter(key=self.tag)]
    
    def get_query_set(self, queryset):
        from sentry.models import MessageIndex
        kwargs = {self.tag: self.get_value()}
        if self.tag.startswith('data__'):
            return MessageIndex.objects.get_for_queryset(queryset, **kwargs)
        return queryset.filter(**kwargs)
    
    def process(self, data):
        return data
    
    def render(self):
        widget = self.get_widget()
        return widget.render(self.get_value())

class Choice(Filter):
    widget = ChoiceWidget
