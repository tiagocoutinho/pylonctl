#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the pylonctl project
#
# Copyright (c) 2020 Tiago Coutinho
# Distributed under the LGPLv3 license. See LICENSE for more info.

"""The setup script."""

import sys
from setuptools import setup, find_packages

def get_readme(name='README.md'):
    """Get readme file contents"""
    with open(name) as f:
        return f.read()

readme = get_readme()

requirements = ['click', 'prompt_toolkit>=3', 'beautifultable', 'treelib',
                'pypylon', 'numpy', 'PyQt5']

test_requirements = ['pytest', 'pytest-cov']

setup_requirements = []

needs_pytest = {'pytest', 'test'}.intersection(sys.argv)
if needs_pytest:
    setup_requirements.append('pytest-runner')

setup(
    author="Jose Tiago Macara Coutinho",
    author_email='coutinhotiago@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="pylon control CLI",
    entry_points={
        'console_scripts': [
            'pylonctl = pylonctl.cli:cli',
        ],
    },
    install_requires=requirements,
    license="LGPL",
    long_description=readme,
    long_description_content_type='text/markdown',
    include_package_data=True,
    keywords='pylon,CLI',
    name='pylonctl',
    packages=find_packages(),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    python_requires='>=3.7',
    url='https://gitlab.com/tiagocoutinho/pylonctl',
    version='0.1.0'
)
