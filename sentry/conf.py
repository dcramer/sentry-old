from django.conf import settings

import hashlib
import logging
import socket

config = getattr(settings, 'SENTRY_CONFIG', {})

# Allow local testing of Sentry even if DEBUG is enabled
DEBUG = getattr(settings, 'DEBUG', False) and not config.get('DEBUG', False)

THRASHING_TIMEOUT = config.get('THRASHING_TIMEOUT', 60)
THRASHING_LIMIT = config.get('THRASHING_LIMIT', 10)

# Sentry allows you to specify an alternative search backend for itself
SEARCH_ENGINE = config.get('SEARCH_ENGINE', None)
SEARCH_OPTIONS = config.get('SEARCH_OPTIONS', {})
SEARCH_UPDATES = config.get('SEARCH_UPDATES', 'realtime')

FILTERS = config.get('FILTERS', filter(None, (
    SEARCH_ENGINE and 'sentry.filters.SearchFilter' or None,
    'sentry.filters.StatusFilter',
    'sentry.filters.LoggerFilter',
    'sentry.filters.LevelFilter',
    'sentry.filters.ServerNameFilter',
    'sentry.filters.SiteFilter',
)))

KEY = config.get('KEY', hashlib.md5(settings.SECRET_KEY).hexdigest())

LOG_LEVELS = (
    (logging.DEBUG, 'debug'),
    (logging.INFO, 'info'),
    (logging.WARNING, 'warning'),
    (logging.ERROR, 'error'),
    (logging.FATAL, 'fatal'),
)

# This should be the full URL to sentries store view
# XXX: REMOTE_* should be passed as a setting to the client not a global
REMOTE_URL = config.get('REMOTE_URL', None)

if REMOTE_URL:
    if isinstance(REMOTE_URL, basestring):
        REMOTE_URL = [REMOTE_URL]
    elif not isinstance(REMOTE_URL, (list, tuple)):
        raise ValueError("Sentry::REMOTE_URL must be of type list.")

REMOTE_TIMEOUT = config.get('REMOTE_TIMEOUT', 5)

# XXX: this should be configured by a notifications backend
ADMINS = config.get('ADMINS', [])

CLIENT = config.get('CLIENT', 'sentry.client.base.SentryClient')

BACKEND = config.get('BACKEND', {
    'ENGINE': 'sentry.db.backends.redis.RedisBackend',
})

NAME = config.get('NAME', socket.gethostname())

# We allow setting the site name either by explicitly setting it with the
# SENTRY_SITE setting, or using the django.contrib.sites framework for
# fetching the current site. Since we can't reliably query the database
# from this module, the specific logic is within the SiteFilter
SITE = config.get('SITE', None)

# Extending this allow you to ignore module prefixes when we attempt to
# discover which function an error comes from (typically a view)
EXCLUDE_PATHS = config.get('EXCLUDE_PATHS', [])

# By default Sentry only looks at modules in INSTALLED_APPS for drilling down
# where an exception is located
INCLUDE_PATHS = config.get('INCLUDE_PATHS', [])

# Absolute URL to the sentry root directory. Should not include a trailing slash.
URL_PREFIX = config.get('URL_PREFIX', None)

VIEWS = config.get('VIEWS', {
    'errors': {
        'name': 'Exceptions',
        'event': 'sentry.events.ExceptionEvent',
    },
    'messages': {
        'name': 'Messages',
        'event': 'sentry.events.MessageEvent',
    },
    'sql': {
        'name': 'SQL',
        'event': 'sentry.events.QueryEvent',
    },
})
