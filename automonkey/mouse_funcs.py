import sys

import pyautogui
from pyautogui import move  # It is used

WHEEL_DELTA = 120  # one notch of the mouse wheel, in Windows wheel units


def _wheel(notches: int, horizontal: bool = False):
    if sys.platform == "win32":
        # pyautogui.scroll() passes its number to Windows as the raw wheel delta, so
        # scroll(3) moved 3/120 of a notch (nothing visible), and its hscroll() scrolls
        # vertically there. Send whole notches, horizontal ones with MOUSEEVENTF_HWHEEL.
        import ctypes
        pyautogui.failSafeCheck()
        flag = 0x01000 if horizontal else 0x0800  # MOUSEEVENTF_HWHEEL / MOUSEEVENTF_WHEEL
        ctypes.windll.user32.mouse_event(flag, 0, 0, ctypes.c_int(int(notches) * WHEEL_DELTA), 0)
    elif horizontal:
        pyautogui.hscroll(int(notches))
    else:
        pyautogui.scroll(int(notches))


def scrollup(clicks: int):
    """Scrolls up `clicks` notches of the mouse wheel where the mouse is (negative: down)

    Args:
        clicks (int): number of notches
    """
    _wheel(clicks)


def scrollright(clicks: int):
    """Scrolls right `clicks` notches of the horizontal wheel where the mouse is (negative: left)

    Args:
        clicks (int): number of notches
    """
    _wheel(clicks, horizontal=True)


def movedown(distance: int = 10, duration: float = 0.0):
    """Moves the mouse down

    Args:
        distance (int, optional): Distance to move. Defaults to 10.
        duration (float, optional): Duration of the movement in seconds. Defaults to 0.0.
    """
    move(0, int(distance), float(duration))


def moveleft(distance: int = 10, duration: float = 0.0):
    """Moves the mouse left

    Args:
        distance (int, optional): Distance to move. Defaults to 10.
        duration (float, optional): Duration of the movement in seconds. Defaults to 0.0.
    """
    move(-int(distance), 0, float(duration))


def moveright(distance: int = 10, duration: float = 0.0):
    """Moves the mouse right

    Args:
        distance (int, optional): Distance to move. Defaults to 10.
        duration (float, optional): Duration of the movement in seconds. Defaults to 0.0.
    """
    move(int(distance), 0, float(duration))


def moveup(distance: int = 10, duration: float = 0.0):
    """Moves the mouse up

    Args:
        distance (int, optional): Distance to move. Defaults to 10.
        duration (float, optional): Duration of the movement in seconds. Defaults to 0.0.
    """
    move(0, -int(distance), float(duration))
