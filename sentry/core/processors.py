"""
sentry.core.processors
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

class Processor(object):
    def process(self, data):
        resp = self.get_data(data)
        if resp:
            data['extra'].update(resp)
        return data
    
    def get_data(self, data):
        return {}

from pprint import pprint
def sanitize_passwords_processor(data):
    """ Asterisk out passwords from password fields in frames.
    """
    if 'sentry.interfaces.Exception' in data:
        if 'frames' in data['sentry.interfaces.Exception']:
            for frame in data['sentry.interfaces.Exception']['frames']:
                if 'vars' in frame:
                    print frame['vars']
                    for k,v in frame['vars'].iteritems():
                        if k.startswith('password'):
                            frame['vars'][k] = '*'*len(v)
    return data

#class SantizePasswordsProcessor(Processor):
