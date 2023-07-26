"""Python Automation using Mouse and Keyboard, for the masses
"""
from time import sleep
from sys import exit as end

from sys import platform

if platform == "win32":
    from os import startfile  # It is used
elif platform == "linux":
    from subprocess import call
    def startfile(file):
        call(["xdg-open", file])

from clipboard import paste

from pyautogui import click  # It is used
from pyautogui import write  # It is used
from pyautogui import moveTo  # It is used
from pyautogui import mouseUp  # It is used
from pyautogui import confirm
from pyautogui import mouseDown  # It is used
from pyautogui import press as keys  # this normally is to be used for same key left, left, left
from pyautogui import hotkey as keys2  # this is best solution, pass list to be unpacked with *list
from pyautogui import locateOnScreen
from pyautogui import scroll as scrollup  # It is used
from pyautogui import hscroll as scrollright  # It is used
from pyautogui import leftClick as leftclick  # It is used
from pyautogui import rightClick as rightclick  # It is used
from pyautogui import middleClick as middleclick  # It is used
from pyautogui import doubleClick as doubleclick  # It is used
from pyautogui import tripleClick as tripleclick  # It is used
from keyboard import send as keys3  # works mostly on windows - TODO: Check difference to below
from keyboard import press_and_release as keys4  # works mostly on windows

from screeninfo import get_monitors

from .constants import MOUSE_ACTIONS
from .constants import WAIT_ACTIONS
from .constants import KEYBOARD_ACTIONS
from .constants import APPS_ACTIONS
from .constants import IMG_ACTIONS
from .constants import COMMON_APPS

from .exceptions import AutoMonkeyNoAction
from .exceptions import AutoMonkeyNoTarget

from .mouse_tracker import track_mouse
from .mouse_tracker import PositionTracker

if platform == "win32":
    from .app_funcs import open_app
    from .app_funcs import minimize
    from .app_funcs import maximize
    from .app_funcs import close
    from .app_funcs import restore
    from .app_funcs import focus
    from .app_funcs import msoffice_replace
    from .app_funcs import copy

from .mouse_funcs import movedown
from .mouse_funcs import moveleft
from .mouse_funcs import moveright
from .mouse_funcs import moveup

from .img_funcs import _add_ext
from .img_funcs import is_on_screen
from .img_funcs import get_center
from .img_funcs import diagonal_point

from .utils import waitwhile
from .utils import waituntil
from .utils import pastetext
from .utils import copy_from
from .utils import scrolldown
from .utils import scrollleft
from .utils import copy_from_to


ALL_ACTIONS = MOUSE_ACTIONS + KEYBOARD_ACTIONS + WAIT_ACTIONS + APPS_ACTIONS + IMG_ACTIONS

def _wait_for_target(target: any, skip: bool = False):
    """Wait for a target to be available"""
    slept = 0
    while not is_on_screen(target) and not skip:
        sleep(0.1)
        slept += 0.1
        if int(slept) == 30:  # For production make it 300
            stop = confirm("Next target was not found for 5 minutes.\
                           Would you like to continue or stop?",
                           "Continue?",
                           ["Continue", "Stop"])
            if stop == "Stop":
                end()


def _prepare_step(raw_step: dict) -> dict:
    """Transform the raw step into a step that can be used by the script

    Args:
        raw_step (dict): The raw step from the json file

    Raises:
        AutoMonkeyNoAction: If the action is not supported
        AutoMonkeyNoTarget: If the target is not supported

    Returns:
        dict: The step that can be used by the script
    """
    step = dict(
        action=None,
        target=None,
        skip=False,
        wait=0,
        confidence=0.9,
        v_offset=0,
        h_offset=0,
        offset=None,
        monitor=1,
    )

    for arg_pair in raw_step.items():
        step["action"] = arg_pair[0] if arg_pair[0] in ALL_ACTIONS else step["action"]
        step["target"] = arg_pair[1] if arg_pair[0] in ALL_ACTIONS else step["target"]
        step["skip"] = bool(arg_pair[1]) if arg_pair[0] == 'skip' else step["skip"]
        step["wait"] = float(arg_pair[1]) if arg_pair[0] == 'wait' else step["wait"]
        step["confidence"] = float(arg_pair[1]) if arg_pair[0] == 'confidence' else step["confidence"]
        step["v_offset"] = int(arg_pair[1]) if arg_pair[0] == 'v_offset' else step["v_offset"]
        step["h_offset"] = int(arg_pair[1]) if arg_pair[0] == 'h_offset' else step["h_offset"]
        step["offset"] = str(arg_pair[1]) if arg_pair[0] == 'offset' else step["offset"]
        step["monitor"] = arg_pair[1] if arg_pair[0] == 'monitor' else step["monitor"]

    if step["action"] not in ALL_ACTIONS:
        raise AutoMonkeyNoAction(step["action"])

    if step["target"] is None:
        raise AutoMonkeyNoTarget(step["target"])
    return step

def __run_1(step: dict):
    step["target"] = _add_ext(step["target"])
    _wait_for_target(step["target"], step["skip"])

    bullseye = locateOnScreen(step["target"], confidence=step["confidence"])
    bullseye = get_center(bullseye)
    bullseye = diagonal_point(bullseye, step["h_offset"], step["v_offset"])
    if step["offset"] not in ("", None):
        globals()["_offset_clicks"](bullseye, step["target"], step["offset"], step["action"])
    else:
        globals()[step["action"]](bullseye)

def __run_2(step: dict):
    if step["action"] in ("keys2", "msoffice_replace"):
        globals()[step["action"]](*step["target"])
    elif step["action"] == "paste":
        pastetext(paste())
    elif step["action"] == "open_app":
        __run_3(step)
    else:
        globals()[step["action"]](step["target"])

def __run_3(step: dict):
    if step["target"].lower() in COMMON_APPS:
        globals()[step["action"]](COMMON_APPS[step["target"].lower()])
    else:
        globals()[step["action"]](step["target"])

def __monitors():
    monitors = {}
    for _, mon in enumerate(sorted([(mon.x, mon.y) for mon in get_monitors()], key=lambda tup: tup[0])):
        monitors[_] = (mon[0], mon[1])
    return monitors

def __target_1(step: dict):
    step["target"] = step["target"].split("+") if step["action"] in ("keys", "keys2") else step["target"]
    return step

def __target_2(step: dict):
    monitors = __monitors()
    try:
        if step["action"] in ("keys", "keys2") and isinstance(step["target"], tuple):
            step["target"] = (step["target"][0] + monitors[step["monitor"] - 1][0], step["target"][1]) if step["target"][0] < monitors[1][0] else step["target"]
            return step
    except IndexError:
        pass
    except KeyError:
        pass
    return step

def __run_1_cond(step: dict):
    return step["action"] in MOUSE_ACTIONS and not isinstance(step["target"], tuple) and not isinstance(step["target"], int)

def __debug_1(debug: bool, step: dict):
    if debug:
        print(step)

def chain(*steps: dict, debug=False):
    """Chain together a series of automation steps

    Args:
        *steps (dict): Unlimitted number of automation steps as dictionaries.
        Each automation step should be a dictionary with 1 or more pairs:
            - First pair is the Action - Target pair. The only mandatory pair.
              Example: dict(click: "image.jpg") or {"click": "image.jpg"}
            - Next possible pairs are optional:
                * skip (True/False) - optional. If True, the step will be skipped if the target is not found.
                * wait - Seconds to wait after performing the action. Defaults to zero.
                * confidence - optional. Used only for actions on images. Confidence on locating the image.
                  Defaults to 0.9
                * v_offset - optional. Vertical offset from the center of the target.
                * h_offset - optional. Horizontal offset from the center of the target.
                * offset - optional. Offset from the center of the target. Overrides v_offset and h_offset.
                * monitor - optional. Monitor number to perform the action on. Defaults to 1.

        Example of steps:
            chain(
                dict(write="this string", wait=0.5),
                dict(write="this other string"),
                dict(click="C:\\Folder1\\Folder2\\image.jpg", wait=2, confidence=0.8),
                debug=True)

        debug (bool, optional): Debug variable, if True will print each step. Defaults to False.

        Notes:
        1. To use the scroll functions you have to select the scrollable area first
        2. Horizontal scroll (left, right) is not supported on Windows
        3. write function cannot write special characters like German or Chinese characters.
        4. startfile keeps the file opened only until the end of the chain.
           If you want to keep the file opened you need to perform other operations on it.
        5. When using startfile you are responsible for saving and closing the file.
        6. For the app functions (start, close, minimize, maximize, restore, focus) you need to provide the title of the window.add()
           You can also use regex to match the title.

    """
    for _ in steps:
        step = _prepare_step(_)
        __debug_1(debug, step)

        step = __target_1(step)
        step = __target_2(step)

        if __run_1_cond(step):
            __run_1(step)
        else:
            __run_2(step)

        sleep(step["wait"])
