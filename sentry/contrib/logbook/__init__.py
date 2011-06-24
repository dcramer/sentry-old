import logbook

from sentry import capture

class SentryLogbookHandler(logbook.Handler):
    def emit(self, record):

        # TODO: level should be a string
        tags = (('level', record.level), ('logger', record.channel))
        
        if record.exc_info:
            return capture('Exception', exc_info=record.exc_info, tags=tags)
        return capture('Message', message=record.message, tags=tags)

