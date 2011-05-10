import sys

class WSGIErrorMiddleware(object):
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        try:
            return self.application(environ, start_response)
        except Exception:
            exc_info = sys.exc_info()
            self.handle_exception(exc_info, environ)
            exc_info = None
            raise

    def handle_exception(self, exc_info, environ):
        from sentry import capture
        event_id = capture('sentry.events.ExceptionEvent', exc_info=exc_info)
        return event_id
