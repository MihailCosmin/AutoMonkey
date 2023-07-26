#!/usr/bin/env python
"""The setup script."""
from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = "requirements.txt"
with open(requirements, "r", encoding="utf-8") as _:
    requirements = _.read().splitlines()

test_requirements = ['pytest>=3', ]

setup(
    author="Mihail-Cosmin Munteanu",
    author_email='munteanumihailcosmin@gmail.com',
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Python Automation using Mouse and Keyboard for the masses",
    entry_points={
        'console_scripts': [
            'automonkey=automonkey.cli:main',
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='automonkey',
    name='automonkey',
    packages=find_packages(include=['automonkey', 'automonkey.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/MihailCosmin/automonkey',
    version="0.2.1",
    zip_safe=False,
)
