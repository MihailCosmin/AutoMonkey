from os import system
from os.path import isdir

from shutil import rmtree

# User: __token__

if isdir('dist'):
    rmtree('dist')

if isdir('AutoMonkey.egg-info'):
    rmtree('AutoMonkey.egg-info')

system("py -m build")

system("python -m twine upload --repository pypi dist/*")