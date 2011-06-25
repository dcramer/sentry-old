from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to

urlpatterns = patterns('',
    (r'^example/$', redirect_to, {'url': 'http://www.example.com'}),
)