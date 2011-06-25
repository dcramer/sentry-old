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