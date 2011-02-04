import sys
import logging
import warnings

from django.core.signals import got_request_exception
from django.db import  transaction
from django.http import Http404

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

        if request:
            data = dict(
                META=request.META,
                POST=request.POST,
                GET=request.GET,
                COOKIES=request.COOKIES,
            )
        else:
            data = dict()

        extra = dict(
            url=request and request.build_absolute_uri() or None,
            data=data,
        )

        client = get_client()
        client.create_from_exception(**extra)
    except Exception, exc:
        try:
            logger.exception(u'Unable to process log entry: %s' % (exc,))
        except Exception, exc:
            warnings.warn(u'Unable to process log entry: %s' % (exc,))

got_request_exception.connect(sentry_exception_handler)

