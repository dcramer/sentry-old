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

==========
Basic Docs
==========

We'll move all of this into the Sphinx docs once APIs are finalized.

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

----------
Client API
----------

The client is the core of Sentry, which is composed of the ``sentry`` namespace, and its many
submodules. There are a few key things that make up the client:

* ``sentry.client``
* ``sentry.events``
* ``sentry.filters``

Most of these components are also used within ``sentry.web`` as well.

To capture an error, Sentry provides the ``capture`` function:

::

    from sentry import capture
    capture('sentry.events.Exception', exc_info=exc_info)

For built-in events, you can drop the module namespace:

::

    from sentry import capture
    capture('Exception', exc_info=exc_info)

One of the big changes from Sentry 1.x to 2.x, is the ability to record durations (in ms) with events:

::

    from sentry import capture
    capture('Query', query='SELECT * FROM table', engine='psycopg2', time_spent=36)

The other major change, is that labels like "logger", and "server" are now part of the tagging architecture:

::

    from sentry import capture
    capture('Message', message='hello world', tags=[('logger', 'root'), ('level', 'error'), ('url', 'http://example.com')])

------------
What's Left?
------------

This is a rough list of features/APIs which need to be completed (this is better described in the issue tracker):

* Runtime validation of settings (ensure events and filters are valid importables, etc.)
* Filter API
* Plugin API
* Custom Views (still using the old "render everything" logic from Sentry 1.x)
  * Partially done -- we need to deal with non-magical indexes (e.g. explicit, only index this)
* Dashboard View
* Django Integration (some draft code is present)
* SQLAlchemy Backend
* Full test coverage should exist for Models and Backends
* Deal with expiration (since we use sorted sets in Redis, we cant just expires on keys)
* Create a background process which gets launched in addition to the web process
  * Should handle tasks like "expire message"
  * Could handle all API requests?
  