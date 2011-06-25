"""
sentry.core.cleaner
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from sentry import app
from sentry.models import Group, Event

import logging
import datetime
import time
import threading

class Cleaner(threading.Thread):
    """
    Manages cleaning up expired messages.
    """
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger('sentry.core.cleaner')
        super(Cleaner, self).__init__()

    def run(self):
        while True:
            time.sleep(5)

            if not app.config['TRUNCATE_AFTER']:
                continue
            
            cutoff = datetime.datetime.now() - app.config['TRUNCATE_AFTER']
            # XXX: this could be more efficient if we took interest in what
            # groups an event is part of, and checked them while iterating the events
            for event in Event.objects.order_by('date')[:100]:
                if event.date > cutoff:
                    continue

                self.logger.debug('Cleaning up %r' % event)
                event.delete()

            for group in Group.objects.order_by('last_seen')[:100]:
                if group.last_seen > cutoff:
                    continue

                self.logger.debug('Cleaning up %r' % group)
                group.delete()
