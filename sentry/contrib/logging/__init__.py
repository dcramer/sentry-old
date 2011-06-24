from __future__ import absolute_import

import logging

from sentry import capture

class SentryHandler(logging.Handler):
    def emit(self, record):
        capture('Message', message=record.msg, params=record.args)
