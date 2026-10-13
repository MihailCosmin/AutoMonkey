#!/usr/bin/env python
"""The setup script.

The control actions (click_control, type_in_control, ...) need pywinauto on Windows
(listed in requirements.txt, sys_platform == 'win32' only) and AT-SPI on Linux. AT-SPI's
Python bindings (PyGObject/gi) are not listed here or as a pip extra: they come from the
distro, not PyPI, and installing them with pip needs system build dependencies (cairo,
gobject-introspection headers, pkg-config) that aren't guaranteed to be present. Install
instead: `sudo apt-get install python3-gi gir1.2-atspi-2.0 at-spi2-core` (Debian/Ubuntu/
Raspberry Pi OS) and enable accessibility - see the README's Control actions section and
pywinauto_for_linux.md for the rest (Qt/Chrome/Electron flags, Wayland limits, ...).
"""
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
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
    ],
    description="Python Automation using Mouse and Keyboard for the masses",
    entry_points={
        'console_scripts': [
            'automonkey=automonkey.cli:main',
            'automonkey-ai=automonkey.ai.__main__:main',
            'automonkey-mcp=automonkey.ai.mcp_server:main',
        ],
    },
    install_requires=requirements,
    extras_require={'ai': ['mcp>=2.0']},
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='automonkey',
    name='automonkey',
    packages=find_packages(include=['automonkey', 'automonkey.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/MihailCosmin/automonkey',
    version="0.4.1",
    zip_safe=False,
)
