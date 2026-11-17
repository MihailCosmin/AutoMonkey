.. highlight:: shell

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/MihailCosmin/automonkey/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

automonkey could always use more documentation, whether as part of the
official automonkey docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/MihailCosmin/automonkey/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up `automonkey` for local development.

1. Fork the `automonkey` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/automonkey.git

3. Install your local copy into a virtualenv. Assuming you have virtualenvwrapper installed, this is how you set up your fork for local development::

    $ mkvirtualenv automonkey
    $ cd automonkey/
    $ python setup.py develop

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the
   tests. There is no CI on GitHub: these checks are the only ones, run them before
   you push::

    $ flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    $ pytest tests/test_<what you changed>.py
    $ tox

   To get flake8, pytest and tox, pip install requirements_dev.txt into your virtualenv.
   The Linux AT-SPI integration tests run on a Linux desktop or under Xvfb::

    $ AUTOMONKEY_ATSPI_INTEGRATION=1 xvfb-run -a dbus-run-session -- pytest tests/test_atspi_integration.py

6. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

7. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
3. The pull request should work for Python 3.8 and newer, on Windows and Linux. Say in
   the pull request which checks you ran and on which systems (nothing runs them on
   GitHub).

Tips
----

To run a subset of tests::

$ pytest tests.test_automonkey


Deploying
---------

A reminder for the maintainers on how to deploy. Releases are made from the
maintainer's machine (no GitHub Actions). Make sure all your changes are committed
and pushed (including an entry in HISTORY.rst) and the checks above pass. Then run::

$ python publish_pypi.py --dry-run   # build and twine check only
$ python publish_pypi.py             # upload pyproject.toml's version, then bump it
$ git add pyproject.toml
$ git commit -m "Bump version to X.Y.Z"
$ git push

The upload needs a PyPI API token for the project (user ``__token__``).
