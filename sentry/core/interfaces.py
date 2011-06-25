class Interface(object):
    """
    An interface is a structured represntation of data, which may
    render differently than the default ``extra`` metadata in an event.
    """
    def serialize(self):
        raise NotImplementedError

class Http(Interface):
    def __init__(self, url, method, data={}, querystring=None, **kwargs):
        self.url = url
        self.method = method
        self.data = data
        self.querystring = querystring
    
    def serialize(self):
        return {
            'url': self.url,
            'method': self.method,
            'data': self.data,
            'querystring': self.querystring,
        }
