"""
sentry.contrib.logbook
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logbook

from sentry import capture

class SentryHandler(logbook.Handler):
    def emit(self, record):
        tags = (('level', logbook.get_level_name(record.level).lower()), ('logger', record.channel))
        
        if record.exc_info:
            return capture('Exception', exc_info=record.exc_info, tags=tags)
        return capture('Message', message=record.message, tags=tags)

