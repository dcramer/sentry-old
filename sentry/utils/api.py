from sentry import app, VERSION

import hashlib
import hmac

def get_signature(message, timestamp):
    return hmac.new(app.config['KEY'], '%s %s' % (timestamp, message), hashlib.sha1).hexdigest()

def get_auth_header(signature, timestamp, client):
    return 'Sentry sentry_signature=%s, sentry_timestamp=%s, sentry_client=%s' % (
        signature,
        timestamp,
        VERSION,
    )

def parse_auth_header(header):
    return dict(map(lambda x: x.strip().split('='), header.split(' ', 1)[1].split(',')))