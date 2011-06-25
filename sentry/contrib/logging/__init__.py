"""
sentry.contrib.logging
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

from sentry import capture

class SentryHandler(logging.Handler):
    def emit(self, record):
        tags = (('level', record.levelname.lower()), ('logger', record.name))
        
        if record.exc_info:
            return capture('Exception', exc_info=record.exc_info, tags=tags)
        return capture('Message', message=record.msg, tags=tags)
