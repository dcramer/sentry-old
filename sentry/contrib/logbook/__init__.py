import logbook

import sys

class SentryLogbookHandler(logbook.Handler):
    def emit(self, record):
        from sentry import capture

        # Avoid typical config issues by overriding loggers behavior
        if record.name == 'sentry.errors':
            print >> sys.stderr, "Recursive log message sent to SentryHandler"
            print >> sys.stderr, record.message
            return

        kwargs = dict(
            message=record.message,
            level=record.level,
            logger=record.channel,
            data=record.extra,
        )
        if record.exc_info:
            return capture('sentry.events.ExceptionEvent', exc_inf=record.exc_info, **kwargs)
        return capture('sentry.events.MessageEvent', **kwargs)

