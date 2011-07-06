#!/usr/bin/env python
"""
Sentry
~~~~~~

Sentry is a real-time logging platform.

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

install_requires = [
    'Flask',
    'Flask-Babel',
    'redis',
    # python-daemon and eventlet are required to run the Sentry indepenent webserver
    'python-daemon>=1.6',
    'eventlet>=0.9.15',
    'simplejson',
]

try:
    __import__('uuid')
except ImportError:
    # uuid ensures compatibility with older versions of Python
    install_requires.append('uuid')

tests_require = [
    'Django>=1.2,<1.4',
    'django-celery',
    'logbook',
    'nose',
    'unittest2',
]

setup(
    name='sentry',
    version='2.0.0-alpha',
    author='David Cramer',
    author_email='dcramer@gmail.com',
    url='http://github.com/dcramer/django-sentry',
    description = 'Exception Logging to a Database in Django',
    long_description=__doc__,
    packages=find_packages(exclude=["example_project", "tests"]),
    zip_safe=False,
    license='BSD',
    install_requires=install_requires,
    dependency_links=[],
    tests_require=tests_require,
    extras_require={'test': tests_require},
    test_suite='nose.collector',
    include_package_data=True,
    entry_points = {
        'console_scripts': [
            'sentry = sentry.scripts.runner:main',
        ],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
