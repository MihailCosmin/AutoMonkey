#!/usr/bin/env python
"""Compatibility shim - all packaging metadata lives in pyproject.toml.

This file only exists so that `python setup.py <cmd>` keeps working for anyone with that
habit (and for tools that insist on finding a setup.py). Don't add metadata back here:
setuptools reads [project] from pyproject.toml and *ignores* the duplicated values passed
to setup(), which is exactly how the version drifted - setup.py said 0.4.1 while the
sdist/wheel built from that same tree were named 0.3.4 (pyproject.toml's value).

The control actions need pywinauto on Windows (requirements.txt, sys_platform == 'win32')
and AT-SPI on Linux. AT-SPI's Python bindings (PyGObject/gi) are not listed as a pip
dependency here: they come from the distro, not PyPI, and installing them with pip needs
system build dependencies (cairo, gobject-introspection headers, pkg-config) that aren't
guaranteed to be present. Install instead:
`sudo apt-get install python3-gi gir1.2-atspi-2.0 at-spi2-core` (Debian/Ubuntu/Raspberry
Pi OS) and enable accessibility - see README.md ("Control actions") and
docs/linux_atspi.md for the rest (Qt/Chrome/Electron flags, Wayland limits, ...).
"""
from setuptools import setup

setup()