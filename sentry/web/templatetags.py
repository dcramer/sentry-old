"""
sentry.web.templatetags
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from sentry import app
#from sentry.plugins import GroupActionProvider

from flaskext.babel import ngettext, gettext
from jinja2 import Markup, escape

import datetime
import simplejson

@app.template_filter()
def maybe_link(value):
    if value.startswith('http') and '://' in value:
        value = escape(value)
        return Markup(u'<a href="%s">%s</a>' % (value, value))
    return value

@app.template_filter()
def as_sorted(value):
    return sorted(value)

@app.template_filter()
def is_dict(value):
    return isinstance(value, dict)

@app.template_filter()
def with_priority(result_list, key='score'):
    if result_list:
        if isinstance(result_list[0], dict):
            _get = lambda x, k: x[k]
        else:
            _get = lambda x, k: getattr(x, k, 0)

        min_, max_ = min([_get(r, key) for r in result_list]), max([_get(r, key) for r in result_list])
        mid = (max_ - min_) / 4
        for result in result_list:
            val = _get(result, key)
            if val > max_ - mid:
                priority = 'veryhigh'
            elif val > max_ - mid * 2:
                priority = 'high'
            elif val > max_ - mid * 3:
                priority = 'medium'
            elif val > max_ - mid * 4:
                priority = 'low'
            else:
                priority = 'verylow'
            yield result, priority

@app.template_filter()
def num_digits(value):
    return len(str(value))

@app.template_filter()
def chart_data(group, max_days=90):
    return {}
    hours = max_days*24

    today = datetime.datetime.now().replace(microsecond=0, second=0, minute=0)
    min_date = today - datetime.timedelta(hours=hours)

    if get_db_engine(getattr(conn, 'alias', 'default')).startswith('oracle'):
        method = conn.ops.date_trunc_sql('hh24', 'datetime')
    else:
        method = conn.ops.date_trunc_sql('hour', 'datetime')

    chart_qs = list(group.message_set.all()\
                      .filter(datetime__gte=min_date)\
                      .extra(select={'grouper': method}).values('grouper')\
                      .annotate(num=Count('id')).values_list('grouper', 'num')\
                      .order_by('grouper'))

    if not chart_qs:
        return {}

    rows = dict(chart_qs)

    #just skip zeroes
    first_seen = hours
    while not rows.get(today - datetime.timedelta(hours=first_seen)) and first_seen > 24:
        first_seen -= 1

    return {
        'points': [rows.get(today-datetime.timedelta(hours=d), 0) for d in xrange(first_seen, -1, -1)],
        'categories': [str(today-datetime.timedelta(hours=d)) for d in xrange(first_seen, -1, -1)],
    }

@app.template_filter()
def to_json(data):
    return simplejson.dumps(data)

@app.context_processor
def sentry_version():
    import sentry
    return {'sentry_version': sentry.VERSION}

@app.template_filter()
def get_actions(group):
    # TODO:
    return []

@app.template_filter()
def get_panels(group):
    # TODO:
    return []

@app.template_filter()
def get_widgets(group):
    # TODO:
    return []

# @app.template_filter()
# def get_actions(group):
#     action_list = []
#     for cls in GroupActionProvider.plugins.itervalues():
#         inst = cls(group.pk)
#         action_list = inst.actions(request, action_list, group)
#     for action in action_list:
#         yield action[0], action[1], request.path == action[1]
# 
# @app.template_filter()
# def get_panels(group):
#     panel_list = []
#     for cls in GroupActionProvider.plugins.itervalues():
#         inst = cls(group.pk)
#         panel_list = inst.panels(request, panel_list, group)
#     for panel in panel_list:
#         yield panel[0], panel[1], request.path == panel[1]
# 
# @app.template_filter()
# def get_widgets(group):
#     for cls in GroupActionProvider.plugins.itervalues():
#         inst = cls(group.pk)
#         resp = inst.widget(request, group)
#         if resp:
#             yield resp

@app.template_filter()
def timesince(d, now=None):
    """
    Takes two datetime objects and returns the time between d and now
    as a nicely formatted string, e.g. "10 minutes".  If d occurs after now,
    then "0 minutes" is returned.

    Units used are years, months, weeks, days, hours, and minutes.
    Seconds and microseconds are ignored.  Up to two adjacent units will be
    displayed.  For example, "2 weeks, 3 days" and "1 year, 3 months" are
    possible outputs, but "2 weeks, 3 hours" and "1 year, 5 days" are not.

    Adapted from http://blog.natbat.co.uk/archive/2003/Jun/14/time_since
    """
    if not d:
        return 'Never'
    
    if d < datetime.datetime.now() - datetime.timedelta(days=5):
        return d.date()
    
    chunks = (
      (60 * 60 * 24 * 365, lambda n: ngettext('year', 'years', n)),
      (60 * 60 * 24 * 30, lambda n: ngettext('month', 'months', n)),
      (60 * 60 * 24 * 7, lambda n : ngettext('week', 'weeks', n)),
      (60 * 60 * 24, lambda n : ngettext('day', 'days', n)),
      (60 * 60, lambda n: ngettext('hour', 'hours', n)),
      (60, lambda n: ngettext('minute', 'minutes', n))
    )
    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day)
    if now and not isinstance(now, datetime.datetime):
        now = datetime.datetime(now.year, now.month, now.day)

    if not now:
        if d.tzinfo:
            now = datetime.datetime.now(d.tzinfo)
        else:
            now = datetime.datetime.now()

    # ignore microsecond part of 'd' since we removed it from 'now'
    delta = now - (d - datetime.timedelta(0, 0, d.microsecond))
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since <= 0:
        # d is in the future compared to now, stop processing.
        return d.date()
    for i, (seconds, name) in enumerate(chunks):
        count = since // seconds
        if count != 0:
            break
    s = gettext('%(number)d %(type)s', number=count, type=name(count))

    if s == '0 minutes':
        return 'Just now'
    if s == '1 day':
        return 'Yesterday'
    return s + ' ago'

@app.template_filter(name='truncatechars')
def truncatechars(value, arg):
    """
    Truncates a string after a certain number of chars.

    Argument: Number of chars to truncate after.
    """
    try:
        length = int(arg)
    except ValueError: # Invalid literal for int().
        return value # Fail silently.
    if len(value) > length:
        return value[:length] + '...'
    return value
