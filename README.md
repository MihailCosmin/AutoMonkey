[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=5Q6TUMXS2QJW4)
[![](https://snyk.io/test/github/MihailCosmin/AutoMonkey/badge.svg)](https://snyk.io/test/github/MihailCosmin/AutoMonkey)
[![visitors](https://visitor-badge.laobi.icu/badge?page_id=MihailCosmin.AutoMonkey)](https://github.com/MihailCosmin/AutoMonkey)
[![build](https://github.com/MihailCosmin/AutoMonkey/actions/workflows/python-package.yml/badge.svg)](https://github.com/MihailCosmin/AutoMonkey/actions/workflows/python-package.yml)

# AutoMonkey
<img alt="AutoMonkey" src="https://github.com/MihailCosmin/AutoMonkey/raw/06181954fa23605583d61843226f5f3997157435/img/monkey.ico" width="100px" height="100px"/>

Python Automation using Mouse and Keyboard, for the masses

# Installation

1. From <a href="https://pypi.org/project/AutoMonkey/">pypi</a>:

```
pip install AutoMonkey
```

2. From <a href="https://github.com/MihailCosmin/AutoMonkey">github</a>:

```
pip install git+https://github.com/MihailCosmin/AutoMonkey
```

# Dependencies
#### Automonkey is based on:
- <a href="https://github.com/asweigart/pyautogui">pyautogui</a>

#### Other dependencies:
- PyScreeze
- pyperclip
- clipboard
- keyboard
- screeninfo
- pywin32
- pillow
- opencv-python
- numpy
- pytesseract
- <a href="https://github.com/pywinauto/pywinauto">pywinauto</a> (Windows only, for the control actions)

# Usage
Main function to be used is "chain"  

This will allow you to "chain" together most of the other functions of automonkey.  
Which in turn will enable you to create sequences of mouse and/or keyboard actions in order to automate any given task.

A step can have this structure:

```python

dict(
    <action> = <target>,  # action can be any of the automonkey functions, target on which the action will be performed
    wait = 1,  # wait is an optional parameter, which will wait for the given amount of seconds before executing the next step
    skip = False,  # if True, will skip this step
    confidence = 0.9, # confidence is an optional parameter, Used only for actions on images. Confidence on locating the image.
    v_offset = 0,  # v_offset is an optional parameter, Used only for actions on images. Vertical offset from the center of the image.
    h_offset = 0,  # h_offset is an optional parameter, Used only for actions on images. Horizontal offset from the center of the image.
    offset = 0, # offset is an optional parameter, Used only for actions on images. Offset from the center of the image.
    monitor = 0,  # monitor is an optional parameter, Used only for actions on images. Monitor on which to search for the image.
)

or 

{
    "<action>": "<target>",  # action can be any of the automonkey functions, target on which the action will be performed
    "wait": 1,  # wait is an optional parameter, which will wait for the given amount of seconds before executing the next step
    "skip": False,  # if True, will skip this step
    "confidence": 0.9, # confidence is an optional parameter, Used only for actions on images. Confidence on locating the image.
    "v_offset": 0,  # v_offset is an optional parameter, Used only for actions on images. Vertical offset from the center of the image.
    "h_offset": 0,  # h_offset is an optional parameter, Used only for actions on images. Horizontal offset from the center of the image.
    "offset": 0, # offset is an optional parameter, Used only for actions on images. Offset from the center of the image.
    "monitor": 0,  # monitor is an optional parameter, Used only for actions on images. Monitor on which to search for the image.
}
```

1. You can connect multiple mouse actions together by using the "chain" function. Just by doing this you can generally automate most of the tasks you would do on a daily basis.

    There are 2 main ways to click, either by giving the coordinates of the position where to click or by giving the filename of the image you want to click on

    1.1. Clicking by coordinates
        
    
    1.1.1. In order to find the coordinates of a position on the screen you can use the "track_mouse" function or the PositionTracker class

    ```python
        from automonkey import track_mouse
        track_mouse()
    ```

    <img alt="track_mouse" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/track_mouse.gif" width="416px" height="304px"/>


    ```python
        from automonkey import PositionTracker
        tracker = PositionTracker()
        tracker.start()
    ```

    <img alt="PositionTracker" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/PositionTracker.gif" width="918px" height="574px"/>

    1.2.1. Now that you have the coordinates of the position you want to click on, you can use the "chain" function to click on it


    ```python
        from automonkey import chain
        chain(  
            dict(click=(780, 1175), wait=1),  
            dict(click=(444, 194), wait=1),  
            dict(click=(1892, 110), wait=1),  
            debug=True  
        )
    ```

    <img alt="click" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/click.gif" width="960px" height="576px"/>

    1.2. Clicking by image

    1.2.1. To click on an image you first need to make a screenshot of the area you want to click on and save it somewhere on your computer.
        For this you can use any screenshot tool you want, or you could use monkeyshot: https://github.com/MihailCosmin/monkeyshot
        For example you can make a screenshot of the Edge icon from your toolbar, then we can click on it by using the "chain" function.

    <img alt="edge_toolbar" src="https://github.com/MihailCosmin/AutoMonkey/raw/25eaed263793bf548d42f616e241f435baa9d719/demo/edge_toolbar.jpg" width="33px" height="33px"/>

    1.2.2. Now that we have the image we want to click on, we can use the "chain" function to click on it

    ```python
        chain(
            dict(click="demo/edge_toolbar.jpg"),
            dict(click="demo/google_create_account", wait=1),
            dict(click="demo/personal_use", wait=1),
            debug=True
        )
    ```

    <img alt="click_image" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/click_image.gif" width="918px" height="600px"/>

    1.3. All mouse actions:

        * click
        * rightclick
        * leftclick
        * doubleclick
        * tripleclick
        * scrollup
        * scrolldown
        * scrollleft
        * scrollright

2. You can also connect multiple keyboard actions together by using the "chain" function.

    2.1. Write text - This doesn't work well with non-english character. For this you can use the "pastetext" function.

    ```python
        chain(
            dict(click="demo/notepad.jpg"),
            dict(write="Hello World!"),
            debug=True
        )
    ```

    <img alt="write" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/write.gif" width="918px" height="600px"/>

    2.2. Paste text - This works well with non-english characters

    ```python
        chain(
            dict(click="demo/notepad.jpg"),
            dict(pastetext="Straße"),
            debug=True
        )
    ```

    2.3. Key combinations

    ```python
        chain(
            dict(click="demo/notepad.jpg", wait=1),
            dict(write="Hello World!", wait=1),
            dict(keys2="ctrl+a", wait=1),
            dict(keys2="ctrl+x", wait=1),
            dict(keys2="alt+f4", wait=1),  # close notepad
            debug=True
        )
    ```

    <img alt="keys" src="https://github.com/MihailCosmin/AutoMonkey/raw/1fa19ba4517875d00c08cf320e628669d60714dc/demo/keys.gif" width="918px" height="600px"/>

    2.4. All key actions:

        * write
        * pastetext
        * keys
        * keys2 - best option overall for key combinations
        * keys3
        * keys4
        * copy
        * paste

3. Wait actions:

    3.1. Wait until an image appears on the screen
    This can used when you are waiting for a window to finish loading completely and you don't know exactly how long that would take.

    ```python
        chain(
            dict(click="demo/notepad.jpg"),
            dict(waituntil="demo/notepad_opened.jpg", wait=1),
            dict(write="Hello World!", wait=1),
            debug=True
        )
    ```

    3.2. Wait while an image is on the screen

4. App (window) actions:

    4.1. Open an app

    ```python
        chain(
            dict(open_app="notepad++.exe", wait=1),
            dict(waituntil="demo/notepad_opened.jpg", wait=1),
            dict(write="Hello World!", wait=1),
            debug=True
        )
    ```

    4.2. Close an app

    ```python
        chain(
            dict(open_app="notepad++.exe", wait=1),
            dict(write="Hello World!", wait=1),
            dict(close="Notepad", wait=1),
            debug=True
        )
    ```

    4.3. Minimize an app

    ```python
        chain(
            dict(open_app="notepad++.exe", wait=1),
            dict(write="Hello World!", wait=1),
            dict(minimize="Notepad", wait=1),
            debug=True
        )
    ```

    4.4. Maximize an app

    ```python
        chain(
            dict(open_app="notepad++.exe", wait=1),
            dict(write="Hello World!", wait=1),
            dict(maximize="Notepad", wait=1),
            debug=True
        )
    ```

    4.5. Restore an app

    ```python
        chain(
            dict(open_app="notepad++.exe", wait=1),
            dict(write="Hello World!", wait=1),
            dict(minimize="Notepad", wait=1),
            dict(restore="Notepad", wait=1),
            debug=True
        )
    ```

    4.6. All app actions:

        * open_app
        * close
        * startfile
        * focus
        * minimize
        * maximize
        * restore
        * msoffice_replace
        * copy_from
        * copy_from_to

5. Image actions

    5.1 count_img. With this function you can count how many times one image appears on the screen.

    ```python
        chain(
            dict(count_img="demo/M.jpg", wait=1),  # The result will be copied to the clipboard
            dict(open_app="notepad++.exe", wait=1),
            dict(paste="", wait=1),  # with paste we can paste the text from the clipboard
            debug=True
        )
    ```

    5.2. get_text_from_region

    ```python
        chain(
            dict(get_text_from_region=((136, 121), (189, 140)), wait=1),  # The text will be copied to the clipboard
            dict(open_app="notepad++.exe", wait=1),
            dict(paste="", wait=1),  # with paste we can paste the text from the clipboard
            debug=True
        )
    ```

6. Control actions (Windows: <a href="https://github.com/pywinauto/pywinauto">pywinauto</a>; Linux: AT-SPI; macOS: not implemented yet)

    These find buttons, text boxes and menus through the OS accessibility tree instead of
    coordinates or images, so they keep working when the resolution, theme or window position changes.
    Same function names and arguments on both OSes - a `chain` script using them needs no changes
    to run on either one; only the `backend` argument's value differs (`"uia"`/`"win32"` on Windows,
    `"atspi"` on Linux).

    Every function takes the window title (regex, matched anywhere in the title, like focus/close)
    and a control:
    * a "best match" name: `"Save"`, `"SaveButton"`, `"Edit"`
    * or a dict of search criteria: `{"title": "Save", "control_type": "Button"}`, `{"auto_id": "num7Button"}`

    6.1 Windows (pywinauto)

    Optional for all: `backend="uia"` (default, modern apps) or `"win32"` (older apps), `timeout=10` seconds.

    In chain the target is a tuple of arguments or a dict of keyword arguments:

    ```python
        from automonkey import chain, list_controls

        list_controls("Calculator")  # prints the controls and the names you can use

        chain(
            dict(open_app="calc", wait=1),
            dict(wait_control="Calculator"),
            dict(click_control=("Calculator", {"auto_id": "num7Button"})),
            dict(click_control=("Calculator", {"auto_id": "plusButton"})),
            dict(click_control=("Calculator", {"auto_id": "num5Button"})),
            dict(click_control=dict(window="Calculator", control={"auto_id": "equalButton"}, invoke=True)),
            dict(get_control_text=("Calculator", {"auto_id": "CalculatorResults"})),  # copied to the clipboard
        )

        chain(
            dict(open_app="notepad", wait=1),
            dict(type_in_control=dict(window=" - Notepad$", control={"control_type": "Document"}, text="Hello (world)!")),
            dict(select_menu=(" - Notepad$", "Edit->Select all")),
        )
    ```

    Available functions:
    * start_app - start an application with pywinauto
    * click_control, double_click_control, right_click_control - `invoke=True` presses it without moving the mouse
    * type_in_control - types the text as it is; `literal=False` for pywinauto key syntax (`{ENTER}`, `^a`);
      `pause=0.05` if a slow app loses characters
    * set_control_text, get_control_text
    * select_menu - path separated by `->`, e.g. `"File->Save As..."`
    * select_item - item of a combo box / list
    * check_control, uncheck_control
    * wait_control, control_exists
    * list_controls
    * get_window, get_control - return the pywinauto objects for anything else

    6.2 Linux (AT-SPI)

    Setup (distro packages, not pip - PyGObject needs system build dependencies pip can't
    guarantee): on Debian/Ubuntu/Raspberry Pi OS,

    ```bash
        sudo apt-get install python3-gi gir1.2-atspi-2.0 at-spi2-core
        gsettings set org.gnome.desktop.interface toolkit-accessibility true
    ```

    The `toolkit-accessibility` key only affects apps started *after* it's enabled -
    restart anything already running. Apps must also not have `NO_AT_BRIDGE=1` set in
    their environment, which silently disables AT-SPI registration.

    Not every app exposes an accessibility tree: GTK, GNOME and LibreOffice apps and
    Firefox work out of the box; Qt apps need `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` in
    their environment before they start; Chrome/Electron apps need the
    `--force-renderer-accessibility` flag; self-drawn/custom-rendered UIs (games,
    canvas-based apps) can't expose one at all.

    `control_type` maps to an AT-SPI role, not quite the same names pywinauto uses on
    Windows - confirmed against real GTK widgets, not just the spec (a push button's role
    is `BUTTON`, not `PUSH_BUTTON`, for instance):

    | control_type | AT-SPI role(s) |
    | --- | --- |
    | `Button` | `BUTTON`, `PUSH_BUTTON`, `TOGGLE_BUTTON` |
    | `CheckBox` | `CHECK_BOX` |
    | `RadioButton` | `RADIO_BUTTON` |
    | `ComboBox` | `COMBO_BOX` |
    | `Edit` | `TEXT`, `ENTRY`, `PASSWORD_TEXT` (also a plain GTK text editor's main area - see note below) |
    | `Document` | `DOCUMENT_TEXT`, `DOCUMENT_FRAME`, `DOCUMENT_WEB`, ... (LibreOffice/WebKit-style content) |
    | `Static` | `LABEL` |
    | `MenuItem` | `MENU_ITEM`, `CHECK_MENU_ITEM`, `RADIO_MENU_ITEM`, `TEAROFF_MENU_ITEM` |
    | `Menu` | `MENU`, `POPUP_MENU` |
    | `MenuBar` | `MENU_BAR` |
    | `List` | `LIST`, `LIST_BOX` |
    | `ListItem` | `LIST_ITEM` |
    | `Tab` / `TabControl` | `PAGE_TAB` / `PAGE_TAB_LIST` |
    | `Window` / `Dialog` | `FRAME` / `DIALOG` |

    `auto_id` matches the AT-SPI accessible-id or an `"id"` attribute if the app sets one
    (most GTK apps don't), falling back to the accessible name otherwise.

    Known Wayland limits: AT-SPI tree reading and actions (`invoke=True`, `check_control`,
    `select_menu`, ...) work the same as on X11/Xwayland. What doesn't: mouse clicks
    (`click_control(invoke=False)`) and keyboard injection (`type_in_control`) only reach
    apps running under Xwayland - a native-Wayland client never receives them at all, no
    matter what has focus (confirmed directly: the identical app forced through Xwayland
    via `GDK_BACKEND=x11` works, the native-Wayland instance silently doesn't). Raising/
    activating a window doesn't work either. `click_control(invoke=False)` detects a
    Wayland session and falls back to `invoke=True` with a warning; `type_in_control` has
    no such fallback - use `invoke=True`-based actions where possible, or run the target
    app under Xwayland (`GDK_BACKEND=x11` for GTK apps) if it must be driven by mouse/
    keyboard injection on Wayland.

    ```python
        from automonkey import chain, list_controls

        list_controls("Calculator")  # prints the controls and the names you can use

        chain(
            # a short wait after each click matters here: Atspi.Action.do_action() returns
            # once the D-Bus call completes, not once the app has processed the resulting
            # GTK signal - clicking straight through with no pause silently drops presses
            # (confirmed directly while building this).
            dict(start_app="gnome-calculator", wait=1),
            dict(wait_control="Calculator"),
            dict(click_control=dict(window="Calculator", control={"title": "7", "control_type": "Button"}, invoke=True), wait=0.3),
            dict(click_control=dict(window="Calculator", control={"title": "+", "control_type": "Button"}, invoke=True), wait=0.3),
            dict(click_control=dict(window="Calculator", control={"title": "5", "control_type": "Button"}, invoke=True), wait=0.3),
            dict(click_control=dict(window="Calculator", control={"title": "=", "control_type": "Button"}, invoke=True), wait=0.3),
            dict(get_control_text=("Calculator", {"control_type": "Edit"})),  # copied to the clipboard
        )

        chain(
            # control_type "Edit" (AT-SPI role "text"), not "Document": gnome-text-editor's
            # main area is a plain GtkSourceView widget, same as most GTK text editors -
            # "Document*" roles are for LibreOffice/WebKit-style content, confirmed against
            # a GtkSourceView-based app while building this.
            dict(start_app="gnome-text-editor", wait=1),
            dict(type_in_control=dict(window="Text Editor", control={"control_type": "Edit"}, text="Hello (world)!")),
            dict(get_control_text=("Text Editor", {"control_type": "Edit"})),  # copied to the clipboard
        )
    ```

    `select_menu` isn't shown against gnome-text-editor above: it's a modern GNOME app
    with no traditional File/Edit menu bar at all (confirmed - zero AT-SPI menu-role nodes
    anywhere in its tree), not an AT-SPI limitation. It works the same way as on Windows
    against any app that does have one, e.g. `select_menu("Mousepad", "File->Save As...")`.

    Same available functions as the Windows list above (`backend="atspi"`, the default on
    Linux, instead of `"uia"`/`"win32"`); `get_window`/`get_control` return `Atspi.Accessible`
    objects instead of pywinauto wrappers for anything not covered here.

    See `pywinauto_for_linux.md` in the repo for the full implementation notes (role
    mapping, best-match lookup, the AT-SPI-bus-down detection, known gotchas found while
    building this) if you need to go beyond what's documented above.


# Frequently Asked Questions:

1. I made an image but it doesn't click on it.

    A: Make sure you have not changed resolution of your screen or the theme (dark/light) of the window.


2. Keys combination using "keys" function doesn't work.

    A: Try other keys functions. Preferably "keys2". Other options "keys3", "keys4".
