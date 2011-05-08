#!/usr/bin/env python
import eventlet
import os
import os.path
import sys

from daemon.daemon import DaemonContext
from daemon.runner import DaemonRunner, make_pidlockfile
from eventlet import wsgi
from optparse import OptionParser

from sentry import VERSION, app

class SentryServer(DaemonRunner):
    pidfile_timeout = 10
    start_message = u"started with pid %(pid)d"

    def __init__(self, host=None, port=None, pidfile=None,
                 logfile=None, daemonize=False):
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
        upgrade()
        wsgi.server(eventlet.listen((self.host, self.port)), app)

def cleanup(days=30, logger=None, site=None, server=None):
    from sentry.models import GroupedMessage, Message
    import datetime
    
    ts = datetime.datetime.now() - datetime.timedelta(days=days)
    
    qs = Message.objects.filter(datetime__lte=ts)
    if logger:
        qs.filter(logger=logger)
    if site:
        qs.filter(site=site)
    if server:
        qs.filter(server_name=server)
    qs.delete()
    
    # TODO: we should collect which messages above were deleted
    # and potentially just send out post_delete signals where
    # GroupedMessage can update itself accordingly
    qs = GroupedMessage.objects.filter(last_seen__lte=ts)
    if logger:
        qs.filter(logger=logger)
    qs.delete()

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
        parser.add_option('--days', default='30',
                          help='Numbers of days to truncate on.')
        parser.add_option('--logger',
                          help='Limit truncation to only entries from logger.')
        parser.add_option('--site',
                          help='Limit truncation to only entries from site.')
        parser.add_option('--server',
                          help='Limit truncation to only entries from server.')

    (options, args) = parser.parse_args()

    if options.config:
        os.environ['DJANGO_SETTINGS_MODULE'] = options.config

    # TODO: we should attempt to discover settings modules

    # if not django_settings.configured:
    #     os.environ['DJANGO_SETTINGS_MODULE'] = 'sentry.conf.server'

    if args[0] == 'upgrade':
        upgrade()

    elif args[0] == 'start':
        app = SentryServer(host=options.host, port=options.port,
                           pidfile=options.pidfile, logfile=options.logfile,
                           daemonize=options.daemonize)
        app.execute(args[0])

    elif args[0] == 'restart':
        app = SentryServer()
        app.execute(args[0])
  
    elif args[0] == 'stop':
        app = SentryServer(pidfile=options.pidfile, logfile=options.logfile)
        app.execute(args[0])

    elif args[0] == 'cleanup':
        cleanup(days=options.days, logger=options.logger, site=options.site, server=options.server)

    sys.exit(0)

if __name__ == '__main__':
    main()