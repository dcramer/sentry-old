======
Sentry
======

**SENTRY 2.0 (this) IS IN DEVELOPMENT AND SHOULD NOT BE USED IN PRODUCTION**

Sentry provides you with a generic interface to view and interact with your error logs. By
default, it will record various events to a datastore. With this
it allows you to interact and view near real-time information to discover issues and more
easily trace them in your application.

(The next chunk is a lie, but planned)

Built-in support includes:

- Drop-in Django support
- WSGI middleware for error logging
- Query logging for psycopg2 and MySQLdb
- ``logging`` and ``logbook`` modules

Issue tracker: http://github.com/dcramer/django-sentry/issues

-------------
Running tests
-------------

Sentry uses Nose, which will automatically be installed (along with unittest2) if you use
the ``test`` command.

::

    mkvirtualenv sentry
    python setup.py test

----------------------
Running ``sentry.web``
----------------------

The server component of Sentry, called ``sentry.web``, can be run with the following command:

::

    mkvirtualenv sentry
    python setup.py develop
    sentry start --no-daemon --debug