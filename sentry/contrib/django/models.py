"""
sentry.contrib.django.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

from django.core.signals import got_request_exception

from sentry import capture

def sentry_exception_handler(request=None, **kwargs):
    event_id = capture('Exception')

    if request:
        # attach the sentry object to the request
        request.sentry = {
            'id': event_id,
        }

got_request_exception.connect(sentry_exception_handler)

