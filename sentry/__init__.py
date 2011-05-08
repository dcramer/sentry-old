"""
Sentry
~~~~~~

TODO: Can we merge data + tags?
      - we need the answer to this to be yes
      - tags are generally more generic, could add extra overhead
        unless we specify which keys are going to be filterable
      - do we prefix them with tag_<foo>?
      - do we continue prefixing sentry builtins with s_?
      - do we just prefix sentry builtins with _?

TODO: How do we specify grouping functions?
      - we need to be able to say "show exceptions by url"
        and "show exceptions by function"
      - behavior needs to exist that we can specify some kind of hashing
        function for an event, and the processor should define a default
      - this should replace get_event_hash

Sentry 2 stores events based on tag groups. These groups are defined at
runtime so that future messages can be stored in an optimized pattern
for quick retrieval and aggregation.

An event consists of anything an extension allows, but but could include
things like a website view, a sql query, or a logging message. Events are
formed by processors, which control how they are stored and tagged.

When a event occurs, the client may optionally generate an ID (a standard 32
character UUID) which should be unique to this event, and pass it to the user.
This ID can then be referenced as a point of entry for all events which correlate
to this.

Events can have many tags, and must have a unique 'type' which describe how
this event is rendered. Events of separate types cannot be aggregated
together.

Aggregated events, known as a Group, contain any number of events which contain
an identical checksum (defined by its processor) and tagged based on predefined
sets. For example, one may configure a set as an Exception event grouped by [view].
One could also define a separate set as a Query event grouped by [url]. The list of
tags can be many and any aggregated event should contain all matching tags. Tags
can also be NULL, and NULL should only equate to NULL.

With this data structure, the bare minimum a backend needs to handle in terms of
operations and architecture are:

- get key
- get key relations (e.g. all events tagged with FOO and BAR)
- set key = value
- set key relations = [values]

It's possible that the relational queries could be denormalized so that any standard
key value store is useable. This would mean additional writes in order to store indexes
for all combinations of tags on each event.

Several example use cases for tags:

- level = 'warning'
- function = 'module.function_name'
- url = 'http://...'
- server = 'localhost'
- project = 'my project name'

Views, which determine how things are aggregated and rendered, should be intelligent
with grouping. For example, if you specify the following views:

- exceptions by [project, url]
- queries by [project, url]
- exceptions by [func]

We should be able to determine (automatically?) that we want a top level view of things
broken down by project, and once there, being able to break down those projects by either
exceptions or queries. The one issue which arises here, is that it should be intelligent
enough to know that the length of values for a key should determine if it does the breakdown
or if it simply renders the aggregate views.

Processor Ideas:

- Exception logging (per framework)
- General logging integration (as well as LogBook)
- Query log processing for MySQL and PGSQL

"""

try:
    VERSION = __import__('pkg_resources') \
        .get_distribution('sentry').version
except Exception, e:
    VERSION = 'unknown'

from flask import Flask

from sentry.db import get_backend
from sentry.web.views import frontend

app = Flask(__name__)

# Build configuration
app.config.from_object('sentry.conf.SentryConfig')
app.config.from_envvar('SENTRY_SETTINGS', silent=True)

# Register views
app.register_module(frontend)

app.db = get_backend(app)