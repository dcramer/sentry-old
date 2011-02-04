import datetime
import hashlib

from sentry import conf

_backend = (None, None)

def get_backend():
    global _backend
    if _backend[0] != conf.BACKEND:
        engine = conf.BACKEND['ENGINE']
        module, class_name = engine.rsplit('.', 1)
        _backend = (conf.BACKEND, getattr(__import__(module, {}, {}, class_name), class_name)(**conf.BACKEND.get('OPTIONS', {})))
    return _backend[1]

backend = get_backend()