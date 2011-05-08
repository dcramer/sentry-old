import logbook

class SentryLogbookHandler(logbook.Handler):
    def emit(self, record):
        from sentry.events import store

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
        client = get_client()
        if record.exc_info:
            return store('MessageEvent', exc_inf=record.exc_info, **kwargs)
        return store('MessageEvent', **kwargs)

