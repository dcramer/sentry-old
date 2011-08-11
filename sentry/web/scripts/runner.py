#!/usr/bin/env python
"""
sentry.web.scripts.runner
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import eventlet
import os
import os.path
import sys

from daemon.daemon import DaemonContext
from daemon.runner import DaemonRunner, make_pidlockfile
from eventlet import wsgi
from optparse import OptionParser

from sentry import VERSION, app
from sentry.middleware import WSGIErrorMiddleware

class SentryWeb(DaemonRunner):
    pidfile_timeout = 10
    start_message = u"started with pid %(pid)d"

    def __init__(self, host=None, port=None, pidfile=None,
                 logfile=None, daemonize=False, debug=False):
        if not logfile:
            logfile = app.config['WEB_LOG_FILE']

        logfile = os.path.realpath(logfile)
        pidfile = os.path.realpath(pidfile or app.config['WEB_PID_FILE'])
        
        if daemonize:
            detach_process = True
        else:
            detach_process = False

        self.daemon_context = DaemonContext(detach_process=detach_process)
        self.daemon_context.stdout = open(logfile, 'w+')
        self.daemon_context.stderr = open(logfile, 'w+', buffering=0)

        self.pidfile = make_pidlockfile(pidfile, self.pidfile_timeout)

        self.daemon_context.pidfile = self.pidfile

        self.host = host or app.config['WEB_HOST']
        self.port = port or app.config['WEB_PORT']

        self.debug = debug

        # HACK: set app to self so self.app.run() works
        self.app = self

    def execute(self, action):
        self.action = action
        if self.daemon_context.detach_process is False and self.action == 'start':
            # HACK:
            self.run()
        else:
            self.do_action()

    def run(self):
        # Import views/templatetags to ensure registration
        import sentry.web.templatetags
        import sentry.web.views

        upgrade()
        app.wsgi_app = WSGIErrorMiddleware(app.wsgi_app)

        if self.debug:
            app.run(host=self.host, port=self.port, debug=self.debug)
        else:
            wsgi.server(eventlet.listen((self.host, self.port)), app)

def cleanup(days=30, tags=None):
    from sentry.models import Group, Event
    import datetime
    
    ts = datetime.datetime.now() - datetime.timedelta(days=days)
    
    for event in Event.objects.order_by('date'):
        if event.date > ts:
            break
        event.delete()
    
    for group in Group.objects.order_by('last_seen'):
        if group.last_seen > ts:
            break
        event.delete()


def upgrade():
    pass
    # from sentry.conf import settings
    # 
    # call_command('syncdb', database=settings.DATABASE_USING or 'default', interactive=False)
    # 
    # if 'south' in django_settings.INSTALLED_APPS:
    #     call_command('migrate', database=settings.DATABASE_USING or 'default', interactive=False)

def main():
    command_list = ('start', 'stop', 'restart', 'cleanup', 'upgrade')
    args = sys.argv
    if len(args) < 2 or args[1] not in command_list:
        print "usage: sentry [command] [options]"
        print
        print "Available subcommands:"
        for cmd in command_list:
            print "  ", cmd
        sys.exit(1)

    parser = OptionParser(version="%%prog %s" % VERSION)
    parser.add_option('--config', metavar='CONFIG')
    if args[1] == 'start':
        parser.add_option('--debug', action='store_true', default=False, dest='debug')
        parser.add_option('--host', metavar='HOSTNAME')
        parser.add_option('--port', type=int, metavar='PORT')
        parser.add_option('--daemon', action='store_true', default=False, dest='daemonize')
        parser.add_option('--no-daemon', action='store_false', default=False, dest='daemonize')
        parser.add_option('--pidfile', dest='pidfile')
        parser.add_option('--logfile', dest='logfile')
    elif args[1] == 'stop':
        parser.add_option('--pidfile', dest='pidfile')
        parser.add_option('--logfile', dest='logfile')
    elif args[1] == 'cleanup':
        parser.add_option('--days', default='30', type=int,
                          help='Numbers of days to truncate on.')
        parser.add_option('--tags',
                          help='Limit truncation to only entries tagged with key:value.')

    (options, args) = parser.parse_args()

    if options.config:
        app.config.from_pyfile(options.config)
    else:
        config_path = os.path.expanduser(os.path.join('~', '.sentry', 'sentry.conf.py'))
        if os.path.exists(config_path):
            app.config.from_pyfile(config_path)

    if args[0] == 'upgrade':
        upgrade()

    elif args[0] == 'start':
        web = SentryWeb(host=options.host, port=options.port,
                           pidfile=options.pidfile, logfile=options.logfile,
                           daemonize=options.daemonize, debug=options.debug)
        web.execute(args[0])

    elif args[0] == 'restart':
        web = SentryWeb()
        web.execute(args[0])
  
    elif args[0] == 'stop':
        web = SentryWeb(pidfile=options.pidfile, logfile=options.logfile)
        web.execute(args[0])

    elif args[0] == 'cleanup':
        cleanup(days=options.days, tags=options.tags)

    sys.exit(0)

if __name__ == '__main__':
    main()