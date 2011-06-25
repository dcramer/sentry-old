"""
sentry.client.celery.conf
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

class SentryCeleryConfig(object):
    CELERY_ROUTING_KEY = 'sentry'