=======
History
=======

0.4.0 (2026-10-13)
------------------

* Add a Linux backend (``automonkey/atspi_funcs.py``) for the control actions
  (``click_control``, ``type_in_control``, ``get_control_text``, ``select_menu``, ...),
  using AT-SPI via ``gi.repository.Atspi`` (``python3-gi``, ``gir1.2-atspi-2.0``,
  ``at-spi2-core`` - distro packages, not pip). Same function names and signatures as
  the Windows ``pywinauto_funcs.py`` backend, selected automatically by platform, so a
  ``chain`` script using the control actions needs no changes to run on either OS.
* Known limits on Wayland: mouse clicks and keyboard injection into a control only
  reach apps running under Xwayland, not native Wayland clients; raising/activating a
  window doesn't work either. ``click_control(invoke=False)`` falls back to the AT-SPI
  action and warns when this is detected. See the README's Control actions section.
* Fix: ``copy()`` (used by ``get_control_text``/clipboard helpers) no longer crashes the
  whole call when one of its two clipboard backends raises - pyperclip's auto-detected
  "gtk" backend does, once ``gi.repository`` has been imported in-process.

0.0.2 (2022-11-06)
------------------

* First release on PyPI.
