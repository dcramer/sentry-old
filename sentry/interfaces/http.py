from sentry.interfaces import Interface

class Http(Interface):
    def __init__(self, url, method, data={}, **kwargs):
        self.url = url
        self.method = method
        self.data = data
    
    def serialize(self):
        return {
            'url': self.url,
            'method': self.method,
            'data': self.data,
        }