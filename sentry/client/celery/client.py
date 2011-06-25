"""
sentry.client.celery.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from sentry.client.base import SentryClient
from sentry.client.celery import tasks

class CelerySentryClient(SentryClient):
    def send(self, **kwargs):
        "Errors through celery"
        tasks.send.delay(kwargs)