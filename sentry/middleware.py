"""
sentry.middleware
~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import sys

from sentry import capture
from werkzeug.wsgi import get_current_url

class WSGIErrorMiddleware(object):
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        try:
            return self.application(environ, start_response)
        except Exception:
            exc_info = sys.exc_info()
            self.handle_exception(exc_info, environ)
            exc_info = None
            raise

    def handle_exception(self, exc_info, environ):
        event_id = capture('Exception',
            exc_info=exc_info,
            data={
                'sentry.interfaces.Http': {
                    'method': environ.get('REQUEST_METHOD'),
                    'url': get_current_url(environ, strip_querystring=True),
                    'querystring': environ.get('QUERY_STRING'),
                },
            },
        )
        return event_id
