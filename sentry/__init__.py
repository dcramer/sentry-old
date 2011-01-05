"""
Sentry
~~~~~~

Sentry 2 stores events based on tag groups. These groups are defined at
runtime so that future messages can be stored in an optimized pattern
for quick retrieval and aggregation.

An event consists of anything an extension allows, but but could include
things like a website view, a sql query, or a logging message. Events are
formed by processors, which control how they are stored and tagged.

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
"""

__all__ = ('__version__', '__build__', '__docformat__', 'get_revision')
__version__ = (1, 3, 14)
__docformat__ = 'restructuredtext en'

import os

def _get_git_revision(path):
    revision_file = os.path.join(path, 'refs', 'heads', 'master')
    if not os.path.exists(revision_file):
        return None
    fh = open(revision_file, 'r')
    try:
        return fh.read().strip()
    finally:
        fh.close()

def get_revision():
    """
    :returns: Revision number of this branch/checkout, if available. None if
        no revision number can be determined.
    """
    package_dir = os.path.dirname(__file__)
    checkout_dir = os.path.normpath(os.path.join(package_dir, '..'))
    path = os.path.join(checkout_dir, '.git')
    if os.path.exists(path):
        return _get_git_revision(path)
    return None

__build__ = get_revision()

def get_version():
    base = '.'.join(map(str, __version__))
    if __build__:
        base = '%s (%s)' % (base, __build__)
    return base