from sentry.db import store_event, client

class Processor(object):
    def store(self):
        """Must return a dictionary which will be stored as ``data``"""

    def summarize(self):
        """Must return a dictionary which will be stored as ``Group.data``"""

class LogMessageProcessor(Processor):
    def store(self, message, exc_info=None, url=None, extra=None):
        """
        Params:
        
        - message: a string of the log message
        - exc_info: typically provided by sys.exc_info() (tuple)
        - url: absolute URI where log message occurred
        - extra: dictionary of meta information (such as GET, POST, META)
        """
        return store_event(
            processor=self,
            tags={
                'url': url,
                'view': view,
            },
            data={
                'message': message,
            },
        )
        

    def summarize(self):
        """Returns a dictionary of data that can be used as a summary"""