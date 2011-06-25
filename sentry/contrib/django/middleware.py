"""
sentry.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

from sentry import capture

class Sentry404CatchMiddleware(object):
    def process_response(self, request, response):
        if response.status_code != 404:
            return response
        message_id = capture('Message', message='Http 404 at %s' % (request.build_absolute_uri()), tags=(('level', 'info'), ('logger', 'http404')))
        request.sentry = {
            'id': message_id,
        }
        return response

    # sentry_exception_handler(sender=Sentry404CatchMiddleware, request=request)

class SentryResponseErrorIdMiddleware(object):
    """
    Appends the X-Sentry-ID response header for referencing a message within
    the Sentry datastore.
    """
    def process_response(self, request, response):
        if not getattr(request, 'sentry', None):
            return response
        response['X-Sentry-ID'] = request.sentry['id']
        return response
