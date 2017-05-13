#!/usr/bin/env python2

import os

from distutils.core import setup

setup(
    name = 'PietDbg',
    version = '0.1',
    description = 'Debugger interface for npiet, Piet language interpreter',
    license = 'MIT',
    author = 'dead-beef',
    url = 'https://github.com/dead-beef/pietdbg',
    packages = [ 'libpietdbg' ],
    scripts = [ 'pietdbg' ],
    data_files=[
        ('share/pietdbg', [ 'README.md', 'LICENSE.md' ]),
    ],
)
