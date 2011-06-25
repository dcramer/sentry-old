"""
sentry.core.interfaces
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import urlparse

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
