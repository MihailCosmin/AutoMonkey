"""Manual fallback for publishing from a local checkout.

You normally don't need this: pushing to main publishes to PyPI automatically via
.github/workflows/python-package.yml (job "publish"), using PyPI's trusted publishing, so
no token is involved. Reach for this script only when you must release from your own
machine - it then needs a PyPI API token (user `__token__`, project AutoMonkey), because
trusted publishing only works from GitHub Actions, and the upload will be refused by CI
anyway if that version is already on PyPI.

Note the version this uploads: whatever [project].version holds in pyproject.toml. CI
keeps that at the *next* version to release, and runs `python bump_version.py` for you
after each successful upload.
"""
from os import system
from os.path import isdir
from shutil import rmtree

# User: __token__

if isdir('dist'):
    rmtree('dist')

if isdir('AutoMonkey.egg-info'):
    rmtree('AutoMonkey.egg-info')

# `python -m build`, not `setup.py sdist`: setup.py is now only a compatibility shim and
# every piece of metadata lives in pyproject.toml.
system("python -m build")

system("python -m twine upload --repository pypi dist/*")