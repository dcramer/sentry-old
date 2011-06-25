from .. import BaseTest

from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASE_ENGINE='sqlite3',
        DATABASES={
            'default': {
                'ENGINE': 'sqlite3',
                'TEST_NAME': ':memory:',
            },
        },
        # HACK: this fixes our threaded runserver remote tests
        # DATABASE_NAME='test_sentry',
        # TEST_DATABASE_NAME='test_sentry',
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.admin',
            'django.contrib.sessions',
            'django.contrib.sites',

            # Included to fix Disqus' test Django which solves IntegrityMessage case
            'django.contrib.contenttypes',

            'djcelery', # celery client

            'sentry',
            'sentry.client.django',
        ],
        ROOT_URLCONF='',
        DEBUG=False,
        SITE_ID=1,
        BROKER_HOST="localhost",
        BROKER_PORT=5672,
        BROKER_USER="guest",
        BROKER_PASSWORD="guest",
        BROKER_VHOST="/",
        CELERY_ALWAYS_EAGER=True,
        SENTRY_THRASHING_LIMIT=0,
        TEMPLATE_DEBUG=True,
    )
    import djcelery
    djcelery.setup_loader()

from django.http import HttpRequest
from sentry.contrib.django.models import sentry_exception_handler
from sentry.models import Event

class DjangoTest(BaseTest):
    def test_exception_handler(self):
        request = HttpRequest()
        
        try:
            raise ValueError('foo bar')
        except:
            sentry_exception_handler(request)
        
        self.assertTrue(hasattr(request, 'sentry'))
        
        event_id = request.sentry['id']
        
        event = Event.objects.get(event_id)

        data = event.data

        self.assertTrue('sentry.interfaces.Exception' in data)
        event_data = data['sentry.interfaces.Exception']
        self.assertTrue('value' in event_data)
        self.assertEquals(event_data['value'], 'foo bar')
        self.assertTrue('type' in event_data)
        self.assertEquals(event_data['type'], 'ValueError')
        self.assertTrue('frames' in event_data)
        self.assertEquals(len(event_data['frames']), 1)
        frame = event_data['frames'][0]
        self.assertTrue('function' in frame)
        self.assertEquals(frame['function'], 'test_exception_handler')
        self.assertTrue('lineno' in frame)
        self.assertTrue(frame['lineno'] > 0)
        self.assertTrue('module' in frame)
        self.assertEquals(frame['module'], 'tests.test_contrib.test_django')
        self.assertTrue('id' in frame)
        self.assertTrue('filename' in frame)
