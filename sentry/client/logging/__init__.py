"""
sentry.client.logging
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

from sentry.client.base import SentryClient

import logging
import sys

class LoggingSentryClient(SentryClient):
    logger_name = 'sentry'
    default_level = logging.ERROR
    
    def __init__(self, *args, **kwargs):
        super(LoggingSentryClient, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.logger_name)
    
    def send(self, event_type, data, **kwargs):
        exc_info = sys.exc_info()

        module, class_name = event_type.rsplit('.', 1)

        handler = getattr(__import__(module, {}, {}, [class_name], -1), class_name)()

        message = handler.to_string(data[handler.interface])

        self.logger.log(self.default_level, message, exc_info=True, extra=data)
