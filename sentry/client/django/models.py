from __future__ import absolute_import

import sys
import logging
import warnings

from django.core.signals import got_request_exception
from django.db import transaction

from sentry import conf

logger = logging.getLogger('sentry.errors')

@transaction.commit_on_success
def sentry_exception_handler(request=None, **kwargs):
    try:
        exc_type, exc_value, exc_traceback = sys.exc_info()

        if conf.DEBUG or getattr(exc_type, 'skip_sentry', False):
            return

        if transaction.is_dirty():
            transaction.rollback()

        extra = dict(
            request=request,
        )

        message_id = get_client().create_from_exception(**extra)
        if request:
            # attach the sentry object to the request
            request.sentry = {
                'id': message_id,
            }
    except Exception, exc:
        try:
            logger.exception(u'Unable to process log entry: %s' % (exc,))
        except Exception, exc:
            warnings.warn(u'Unable to process log entry: %s' % (exc,))

got_request_exception.connect(sentry_exception_handler)

