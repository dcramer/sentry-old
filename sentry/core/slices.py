import hashlib

from sentry import app

def all():
    """
    Returns an iterable yielding Slice instances.
    """
    for k, v in app.config['SLICES'].iteritems():
        yield Slice(slug=k, **v)

def get(slug):
    """
    Returns a slice by it's slug.
    """
    return Slice(slug=slug, **app.config['SLICES'][slug])

class Slice(object):
    """
    #     'name': 'Exceptions',
    #     'events': ['sentry.events.Exception'],
    #     'filters': [
    #         ('server', 'sentry.web.filters.Choice'),
    #         ('level', 'sentry.web.filters.Choice'),
    #         ('logger', 'sentry.web.filters.Choice'),
    #     ],
    #     # override the default label 
    #     'labelby': 'url',
    """
    def __init__(self, slug, name=None, events=[], filters=[], labelby=None):
        self.slug = slug
        self.name = name or slug.title()
        self.events = events
        self.filters = filters
        self.labelby = labelby
        self.id = hashlib.md5(slug).hexdigest()
    
    def is_valid_event(self, event_type):
        if not self.events:
            return True
        return event_type in self.events
        