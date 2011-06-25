"""
sentry.interfaces
~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import urlparse

from flask import render_template

# unserialization concept is based on pickle
class _EmptyClass(object):
    pass

def unserialize(klass, data):
    value = _EmptyClass()
    value.__class__ = klass
    value.__setstate__(data)
    return value

class Interface(object):
    """
    An interface is a structured represntation of data, which may
    render differently than the default ``extra`` metadata in an event.
    """

    def __setstate__(self, data):
        self.__dict__.update(self.unserialize(data))

    def __getstate__(self):
        return self.serialize()

    def unserialize(self, data):
        return data
        
    def serialize(self):
        return {}
    
    def to_html(self, event):
        return ''

class Message(Interface):
    def __init__(self, message, params):
        self.message = message
        self.params = params
    
    def serialize(self):
        return {
            'message': self.message,
            'params': self.params,
        }

class Query(Interface):
    def __init__(self, query, engine):
        self.query = query
        self.engine = engine
    
    def serialize(self):
        return {
            'query': self.query,
            'engine': self.engine,
        }

class Exception(Interface):
    def __init__(self, type, value, frames):
        self.type = type
        self.value = value
        self.frames = frames
    
    def serialize(self):
        return {
            'type': self.type,
            'value': self.value,
            'frames': self.frames,
        }
    
    def to_html(self, event):
        return render_template('sentry/partial/interfaces/exception.html', **{
            'exception_value': self.value,
            'exception_type': self.type,
            'frames': self.frames,
        })

class Http(Interface):
    # methods as defined by http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html
    METHODS = ('GET', 'POST', 'PUT', 'OPTIONS', 'HEAD', 'DELETE', 'TRACE', 'CONNECT')
    
    def __init__(self, url, method, data=None, querystring=None, **kwargs):
        if data is None:
            data = {}

        method = method.upper()

        assert method in self.METHODS

        urlparts = urlparse.urlsplit(url)

        if not querystring:
            # define querystring from url
            querystring = urlparts.query

        elif querystring.startswith('?'):
            # remove '?' prefix
            querystring = querystring[1:]

        self.url = '%s://%s%s' % (urlparts.scheme, urlparts.netloc, urlparts.path)
        self.method = method
        self.data = data
        self.querystring = querystring
    
    def serialize(self):
        return {
            'url': self.url,
            'method': self.method,
            'data': self.data,
            'querystring': self.querystring,
        }

    def to_html(self, event):
        return render_template('sentry/partial/interfaces/http.html', **{
            'full_url': '?'.join(filter(None, [self.url, self.querystring])),
            'url': self.url,
            'method': self.method,
            'data': self.data,
            'querystring': self.querystring,
        })
        
