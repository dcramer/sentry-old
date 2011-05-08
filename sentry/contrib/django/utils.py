import django
from django.conf import settings

def get_db_engine(alias='default'):
    has_multidb = django.VERSION >= (1, 2)
    if has_multidb:
        value = settings.DATABASES[alias]['ENGINE']
    else:
        assert alias == 'default', 'You cannot fetch a database engine other than the default on Django < 1.2'
        value = settings.DATABASE_ENGINE
    return value.rsplit('.', 1)[-1]


def get_installed_apps():
    """
    Generate a list of modules in settings.INSTALLED_APPS.
    """
    out = set()
    for app in settings.INSTALLED_APPS:
        out.add(app)
    return out