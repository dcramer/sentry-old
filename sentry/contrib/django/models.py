from __future__ import absolute_import

import sys
import logging
import warnings

from django.core.signals import got_request_exception
from django.db import transaction

from sentry import app

logger = logging.getLogger('sentry.errors')

@transaction.commit_on_success
def sentry_exception_handler(request=None, **kwargs):
    try:
        exc_info = sys.exc_info()

        exc_type, exc_value, exc_traceback = exc_info

        if app.config['DEBUG'] or getattr(exc_type, 'skip_sentry', False):
            return

        if transaction.is_dirty():
            transaction.rollback()

        event_id = app.client.store('ExceptionEvent', exc_info=exc_info)

        if request:
            # attach the sentry object to the request
            request.sentry = {
                'id': event_id,
            }
    except Exception, exc:
        try:
            logger.exception(u'Unable to process log entry: %s' % (exc,))
        except Exception, exc:
            warnings.warn(u'Unable to process log entry: %s' % (exc,))

got_request_exception.connect(sentry_exception_handler)

