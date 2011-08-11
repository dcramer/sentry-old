#!/usr/bin/env python
"""
sentry.scripts.data_faker
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from sentry import VERSION, app, capture
from sentry.interfaces import Http

import os.path
import random
import sys
from optparse import OptionParser

def main():
    parser = OptionParser(version="%%prog %s" % VERSION)
    parser.add_option('--config', metavar='CONFIG')
    parser.add_option('--num', default=100)
    (options, args) = parser.parse_args()

    if options.config:
        app.config.from_pyfile(options.config)
    else:
        config_path = os.path.expanduser(os.path.join('~', '.sentry', 'sentry.conf.py'))
        if os.path.exists(config_path):
            app.config.from_pyfile(config_path)

    exceptions = [ValueError, SyntaxError, KeyError, IndexError, OSError]
    messages = [
        'Old Man, sorry.  What knight live in that castle over there?',
        'You fight with the strength of many men, Sir knight.',
        'A witch!  A witch!  A witch!  We\'ve got a witch!  A witch!',
        'Does wood sink in water?',
        'The wise Sir Bedemir was the first to join King Arthur\'s knights, but other illustrious names were soon to follow',
    ]
    urls = [
        'http://example.com',
        'http://example.com/foo/bar/',
        'http://example.com/foo/bar/?baz=biz',
    ]
    sql_queries = ['SELECT * FROM table', 'INSERT INTO FOO (a, b, c) VALUES (1, 2, 3)', 'TRUNCATE TABLE baz']
    sql_engines = ['psycopg2', 'mysqldb', 'oracle']
    http_methods = Http.METHODS
    
    for n in xrange(options.num):
        x = random.randint(0, 2)
        if x == 0:
            event = 'Exception'
            kwargs = {}
            exc_class = exceptions[n % len(exceptions)]
            exc_value = messages[n % len(messages)]
            try:
                raise exc_class(exc_value)
            except:
                kwargs = {'exc_info': sys.exc_info()}
        elif x == 1:
            event = 'Message'
            kwargs = {'message': messages[n % len(messages)]}
        elif x == 2:
            event = 'Query'
            kwargs = {'query': sql_queries[n % len(sql_queries)], 'engine': sql_engines[n % len(sql_engines)]}

        if random.randint(0, 1) == 1:
            kwargs['data'] = {
                'sentry.interfaces.Http': {
                    'url': urls[n % len(urls)],
                    'method': http_methods[n % len(http_methods)],
                }
            }

        capture(event, **kwargs)

    sys.exit(0)

if __name__ == '__main__':
    main()