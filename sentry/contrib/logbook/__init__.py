"""
sentry.contrib.logbook
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logbook

from sentry import capture

class SentryLogbookHandler(logbook.Handler):
    def emit(self, record):

        # TODO: level should be a string
        tags = (('level', record.level), ('logger', record.channel))
        
        if record.exc_info:
            return capture('Exception', exc_info=record.exc_info, tags=tags)
        return capture('Message', message=record.message, tags=tags)

