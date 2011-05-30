import base64
import datetime
import simplejson
import logging
import time
import warnings
import zlib

from sentry import app
from sentry.utils import is_float
from sentry.utils.api import get_mac_signature, parse_auth_header
from sentry.utils.compat import pickle

from flask import request, abort

@app.route('/api/store/', methods=['POST'])
def store():
    if request.environ.get('AUTHORIZATION', '').startswith('Sentry'):
        auth_vars = parse_auth_header(request.META['AUTHORIZATION'])
        
        signature = auth_vars.get('sentry_signature')
        timestamp = auth_vars.get('sentry_timestamp')

        format = 'json'

        data = request.raw_post_data

        # Signed data packet
        if signature and timestamp:
            try:
                timestamp = float(timestamp)
            except ValueError:
                abort(400, 'Invalid Timestamp')

            if timestamp < time.time() - 3600: # 1 hour
                abort(410, 'Message has expired')

            sig_hmac = get_mac_signature(app.config['KEY'], data)
            if sig_hmac != signature:
                abort(403, 'Invalid signature')
        else:
            abort(401,'Unauthorized')
    else:
        data = request.form.get('data')
        if not data:
            abort(400, 'Missing data')

        format = request.form.get('format', 'pickle')

        if format not in ('pickle', 'json'):
            abort(400, 'Invalid format')

        # Legacy request (deprecated as of 2.0)
        key = request.form.get('key')
        
        if key != app.config['KEY']:
            warnings.warn('A client is sending the `key` parameter, which will be removed in Sentry 2.0', DeprecationWarning)
            abort(403, 'Invalid credentials')

    logger = logging.getLogger('sentry.server')

    try:
        try:
            data = base64.b64decode(data).decode('zlib')
        except zlib.error:
            data = base64.b64decode(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        abort(400, 'Bad data decoding request (%s, %s)' % (e.__class__.__name__, e))

    try:
        if format == 'pickle':
            data = pickle.loads(data)
        elif format == 'json':
            data = simplejson.loads(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        abort(403, 'Bad data reconstructing object (%s, %s)' % (e.__class__.__name__, e))

    # XXX: ensure keys are coerced to strings
    data = dict((str(k), v) for k, v in data.iteritems())

    if 'timestamp' in data:
        if is_float(data['timestamp']):
            data['timestamp'] = datetime.datetime.fromtimestamp(float(data['timestamp']))
        else:
            if '.' in data['timestamp']:
                format = '%Y-%m-%dT%H:%M:%S.%f'
            else:
                format = '%Y-%m-%dT%H:%M:%S'
            data['timestamp'] = datetime.datetime.strptime(data['timestamp'], format)

    # TODO
    store()
    
    return ''