"""
sentry.db.backends.base
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import hashlib
import uuid

class SentryBackend(object):
    def _get_schema_name(self, schema):
        return schema.__name__.lower()

    def _get_composite_key(self, **keys):
        return hashlib.md5(';'.join('%s=%s' % (k, v) for k, v in keys.iteritems())).hexdigest()

    def generate_key(self, schema):
        return uuid.uuid4().hex
