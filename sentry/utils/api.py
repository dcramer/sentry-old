from sentry import VERSION

import binascii
import hashlib
import hmac
import urllib

def get_auth_header(signature, timestamp, client, nonce):
    return 'Sentry sentry_signature=%s, sentry_timestamp=%s, sentry_nonce=%s, sentry_client=%s' % (
        signature,
        timestamp,
        nonce,
        VERSION,
    )

def parse_auth_header(header):
    return dict(map(lambda x: x.strip().split('='), header.split(' ', 1)[1].split(',')))


def get_normalized_params(params):
    """
    Given a list of (k, v) parameters, returns
    a sorted, encoded normalized param string.
    """
    return '&'.join('%s=%s' % (k, urllib.quote(v)) for k, v in sorted(params))

def get_body_hash(params):
    """
    Returns BASE64 ( HASH (text) ).
    """
    norm_params = get_normalized_params(params)

    return binascii.b2a_base64(hashlib.sha1(norm_params).digest())[:-1]

def get_mac_signature(key, norm_request_string):
    """
    Returns HMAC-SHA1 (api secret, normalized request string)
    """
    hashed = hmac.new(str(key), norm_request_string, hashlib.sha1)
    return binascii.b2a_base64(hashed.digest())[:-1]