=======
History
=======

Unreleased
----------

* Keys reach remote desktops (Windows). With the RDP client (mstsc, msrdc) in front,
  ``key``, ``hotkey``, ``keydown`` and ``keyup`` (and ``press``/``hotkey``/``key_down``/
  ``key_up`` in ``key_funcs``) send scan codes only and leave PowerToys remaps alone; text
  stays Unicode. ``AUTOMONKEY_KEYS=auto|scancode|vk`` (default ``auto``). Measured over RDP
  (17.11.2026): Left/Home/End/PgUp/PgDn/Ins/Del lacked the extended flag (MapVirtualKeyEx
  leaves it off) and arrived as numpad keys, and the PowerToys y<->z correction swapped y and
  z remotely. The extended flag is now set for every extended key, locally too.
* ``keydown``/``keyup`` go through ``key_funcs`` instead of pyautogui (virtual key without
  scan code); new ``key_funcs.key_down``/``key_up``.
* A keyboard call stops with ``FocusChanged`` when another program takes the foreground
  while it types.
* ``focus`` no longer falls back to an Alt tap while a remote desktop is in front (the RDP
  client would forward it and the remote menu bar would take the next keys).
* Screenshots copy only the monitor or region they need (GDI), not the whole desktop
  (Pillow ``all_screens``): 1920x1080 in 33 ms instead of 88 ms on three monitors, so
  ``stable``/``change``/``expect_change`` poll faster.
* ``scrollup``/``scrolldown``/``scrollleft``/``scrollright`` (chain API) scroll whole wheel
  notches on Windows (pyautogui took the number as the raw wheel delta, 1/120 of a notch),
  and the horizontal ones scroll horizontally there.

0.4.5 (2026-10-18)
------------------

* AI layer: mouse input through SendInput on Windows (drags, strokes and hover reach
  WinUI/UWP and canvas apps; SetCursorPos moves were invisible to them), dense
  human-like glides, fail-safe kept.
* Per-monitor DPI awareness; screenshots and clicks on any monitor (``monitor N``).
* Windows window handling rewritten on Win32: cloaked windows skipped, real window
  bounds, process name as class, ``focus`` verified (and explains elevated windows),
  ``launch`` handles paths, Store apps and single-instance apps and stops when it
  reuses an already-open window.
* Accessibility helpers (``controls``, ``click_control``, ``drag_control``, ``focused``,
  ``tab_order``, ``clipped``), including menus and popups shown in separate windows.
* Checks for regression scripts: ``expect_text``, ``expect_no_text``, ``expect_window``,
  ``expect_no_window``, ``expect_focus``, ``expect_control``, ``expect_order``,
  ``expect_change``, ``expect_no_clipped`` (retrying for 3 s); ``finally:`` blocks;
  ``kill``; ``save``; ``keydown``/``keyup``; ``mclick``, ``hscroll``, ``stroke``.
* Session log, ``history``, ``replay`` (MCP tools and CLI) with failure screenshots.
* OCR: 2x upscaling for small UI text, search limited to the active window, line
  re-read for short words, accent- and typography-insensitive matching, falls back to
  the accessibility tree.
* MCP: ``list_controls`` no longer writes to the protocol stream; new tools
  ``controls``, ``replay``, ``history``; ``find_text`` searches the active window.
* ``get_window`` says when the app is probably not running and lists the open windows.
* ``install-claude`` command and the ``visual-testing`` Claude skill
  (``skills/visual-testing``).
* Test apps (PySide6, egui) and unit tests.

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
