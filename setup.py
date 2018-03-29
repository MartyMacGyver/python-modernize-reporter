from __future__ import absolute_import
import os
import re
from setuptools import setup

readme = open(os.path.join(os.path.dirname(__file__), 'README.md'), 'r').read()

module_file = open(os.path.join(os.path.dirname(__file__), 'modernize_reporter', '__init__.py'), 'r').read()
version_match = re.search(r"__version__ = ['\"]([^'\"]*)['\"]", module_file, re.M)
if not version_match:
    raise Exception("couldn't find version number")
version = version_match.group(1)

setup(
    name='modernize-reporter',
    author='Martin Falatic',
    author_email='martin@falatic.com',
    version=version,
    url='https://github.com/MartyMacGyver/python-modernize-reporter',
    packages=['modernize_reporter'],
    py_modules=['modernize_reporter'],
    description='Reports the modernization status for hybrid codebases.',
    long_description=readme,
    entry_points={
        'console_scripts': [
            'python-modernize-reporter = modernize_reporter.main:main'
        ]
    },
    zip_safe=False,
    install_requires=[
        'modernize>=0.6',
    ],
    tests_require='nose',
    test_suite='nose.collector',
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ]
)
