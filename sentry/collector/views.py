"""
sentry.web.api
~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import base64
import datetime
import simplejson
import logging
import time

from sentry import app
from sentry.utils import is_float
from sentry.utils.api import get_mac_signature, parse_auth_header

from flask import request, abort

@app.route('/api/store/', methods=['POST'])
def store():
    """
    Accepts a gzipped JSON POST body.
    
    If ``PUBLIC_WRITES`` is truthy, the Authorization header is ignored.
    
    Format resembles the following:
    
    >>> {
    >>>     "event_type": "Exception",
    >>>     "tags": [ ["level", "error"], ["server", "sentry.local"] ],
    >>>     "date": "2010-06-18T22:31:45",
    >>>     "time_spent": 0.0,
    >>>     "event_id": "452dfa92380f438f98159bb75b9469e5",
    >>>     "data": {
    >>>         "culprit": "path.to.function",
    >>>         "version": ["module", "version string"],
    >>>         "modules": {
    >>>             "module": "version string"
    >>>         },
    >>>         "extra": {
    >>>             "key": "value",
    >>>         },
    >>>         "sentry.interfaces.Http": {
    >>>             "url": "http://example.com/foo/bar",
    >>>             "method": "POST",
    >>>             "querystring": "baz=bar&foo=baz",
    >>>             "data": {
    >>>                 "key": "value"
    >>>             }
    >>>         },
    >>>         "sentry.interfaces.Exception": {
    >>>             "type": "ValueError",
    >>>             "value": "An example exception"
    >>>         },
    >>>         "sentry.interfaces.Stacktrace": {
    >>>             "frames": [
    >>>                 {
    >>>                     "filename": "/path/to/filename.py",
    >>>                     "module": "path.to.module",
    >>>                     "function": "function_name",
    >>>                     "vars": {
    >>>                         "key": "value"
    >>>                     }
    >>>                 }
    >>>             ]
    >>>         }
    >>>     }
    >>> }
    """
    has_header = request.environ.get('AUTHORIZATION', '').startswith('Sentry')
    if not (app.config['PUBLIC_WRITES'] or has_header):
        abort(401,'Unauthorized')

    data = request.data

    if has_header:
        auth_vars = parse_auth_header(request.META['AUTHORIZATION'])
    
        signature = auth_vars.get('signature')
        timestamp = auth_vars.get('timestamp')
        nonce = auth_vars.get('nonce')

        # TODO: check nonce

        # Signed data packet
        if signature and timestamp:
            try:
                timestamp = float(timestamp)
            except ValueError:
                abort(400, 'Invalid Timestamp')

            if timestamp < time.time() - 3600: # 1 hour
                abort(410, 'Message has expired')

            if signature != get_mac_signature(app.config['KEY'], data, timestamp, nonce):
                abort(403, 'Invalid signature')
        else:
            abort(401,'Unauthorized')

    logger = logging.getLogger('sentry.web.api.store')

    try:
        data = base64.b64decode(data).decode('zlib')
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        abort(400, 'Bad data decoding request (%s, %s)' % (e.__class__.__name__, e))

    try:
        data = simplejson.loads(data)
    except Exception, e:
        # This error should be caught as it suggests that there's a
        # bug somewhere in the client's code.
        logger.exception('Bad data received')
        abort(403, 'Bad data reconstructing object (%s, %s)' % (e.__class__.__name__, e))

    # XXX: ensure keys are coerced to strings
    data = dict((str(k), v) for k, v in data.iteritems())

    if 'date' in data:
        if is_float(data['date']):
            data['date'] = datetime.datetime.fromtimestamp(float(data['date']))
        else:
            if '.' in data['date']:
                format = '%Y-%m-%dT%H:%M:%S.%f'
            else:
                format = '%Y-%m-%dT%H:%M:%S'
            data['date'] = datetime.datetime.strptime(data['date'], format)

    event, group = app.client.store(**data)
    
    return event.pk
