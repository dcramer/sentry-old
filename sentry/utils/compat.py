"""
sentry.utils.compat
~~~~~~~~~~~~~~~~~~~

Contains compatibility imports (generally c-module replacements)

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import cmath as math
except ImportError:
    import math
