#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

tests_require = [
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
    packages=find_packages(exclude="example_project"),
    zip_safe=False,
    install_requires=[
        'Flask',
        'Flask-Babel',
        # python-daemon and eventlet are required to run the Sentry indepenent webserver
        'python-daemon>=1.6',
        'eventlet>=0.9.15',
        # uuid ensures compatibility with older versions of Python
        'uuid',
    ],
    dependency_links=[
    ],
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
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
