"""
sentry.core.interfaces
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import urlparse

class Interface(object):
    """
    An interface is a structured represntation of data, which may
    render differently than the default ``extra`` metadata in an event.
    """
    def serialize(self):
        raise NotImplementedError

class Http(Interface):
    # methods as defined by http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html
    METHODS = ('GET', 'POST', 'PUT', 'OPTIONS', 'HEAD', 'DELETE', 'TRACE', 'CONNECT')
    
    def __init__(self, url, method, data={}, querystring=None, **kwargs):
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
