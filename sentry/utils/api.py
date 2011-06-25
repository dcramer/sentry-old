"""
sentry.utils.api
~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from sentry import VERSION

import binascii
import hashlib
import hmac

def get_auth_header(signature, timestamp, client, nonce):
    return 'Sentry signature=%s, timestamp=%s, nonce=%s, client=%s' % (
        signature,
        timestamp,
        nonce,
        VERSION,
    )

def parse_auth_header(header):
    return dict(map(lambda x: x.strip().split('='), header.split(' ', 1)[1].split(',')))

def get_mac_signature(key, data, timestamp, nonce):
    """
    Returns BASE64 ( HMAC-SHA1 (key, data) )
    """
    hashed = hmac.new(str(key), '%s %s %s' % (timestamp, nonce, data), hashlib.sha1)
    return binascii.b2a_base64(hashed.digest())[:-1]