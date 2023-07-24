from time import sleep

from sys import platform

if platform == "win32":
    from os import startfile  # It is used
elif platform == "linux":
    from subprocess import call
    def startfile(file):
        call(["xdg-open", file])
from os import system
from os.path import isfile

from re import search

from subprocess import Popen

from win32con import WM_CLOSE
from win32con import SW_RESTORE
from win32con import SW_MINIMIZE
from win32con import SW_MAXIMIZE

from win32gui import IsIconic
from win32gui import ShowWindow
from win32gui import FindWindow
from win32gui import PostMessage
from win32gui import EnumWindows
from win32gui import GetWindowText
from win32gui import SetForegroundWindow

from pyautogui import keyUp
from pyautogui import keyDown
from pyautogui import hotkey as keys2  # this is best solution, pass list to be unpacked with *list

from .utils import copy

def msoffice_replace(replace_this: str, with_this: str, match_case: bool = True, whole_words: bool = True, delay_factor: float = 1):
    """Search and replace in all MS Office Software. No Guarantees.

    Args:
        replace_this (str): string to be replaced
        with_this (str): new string
        delay_factor (float, optional): Delay factor in case
            the default sleep times for waiting that the replacement
            is finished are too fast. Defaults to 1.
    """
    copy(replace_this)
    sleep(0.2 * delay_factor)
    keys2('ctrl', 'h')
    sleep(0.2 * delay_factor)
    if match_case or whole_words:
        keys2('alt', 'm')
        sleep(0.2 * delay_factor)
    if match_case:
        keys2('alt', 'h')
        sleep(0.2 * delay_factor)
    if whole_words:
        keys2('alt', 'y')
        sleep(0.2 * delay_factor)
    keys2('alt', 'n')
    sleep(0.2 * delay_factor)
    keys2('ctrl', 'v')
    sleep(0.2 * delay_factor)
    copy(with_this)
    sleep(0.2 * delay_factor)
    keys2('alt', 'i')
    sleep(0.2 * delay_factor)
    keys2('ctrl', 'v')
    sleep(0.2 * delay_factor)
    keys2('alt', 'a')
    sleep(0.2 * delay_factor)
    keys2('enter')
    sleep(0.2 * delay_factor)
    keys2('enter')
    sleep(0.2 * delay_factor)
    keys2('esc')
    sleep(0.2 * delay_factor)
    keys2('esc')
    sleep(0.2 * delay_factor)


class WindowManager:
    """Window Manager
    """
    def __init__(self):
        self._handle = None

    def get_window_by_class(self, class_name, window_name=None):
        """Find a window by the class name
        """
        self._handle = FindWindow(class_name, window_name)

    def _parse_windows(self, hwnd, pattern):
        """Pass to EnumWindows() to check all opened windows
        """
        if search(pattern, str(GetWindowText(hwnd))) is not None:
            self._handle = hwnd

    def get_window_by_title(self, pattern):
        """Find a window whose title matches the given regex pattern
        """
        self._handle = None
        EnumWindows(self._parse_windows, pattern)

    def focus(self):
        """Bring focus to the selected window
        """
        # SetForegroundWindow works well only after pressing alt
        keyDown('alt')
        SetForegroundWindow(self._handle)
        self.restore()
        keyUp('alt')

    def minimize(self):
        if not IsIconic(self._handle):
            ShowWindow(self._handle, SW_MINIMIZE)

    def restore(self):
        if IsIconic(self._handle):
            ShowWindow(self._handle, SW_RESTORE)

    def maximize(self):
        ShowWindow(self._handle, SW_MAXIMIZE)

    def close(self):
        PostMessage(self._handle, WM_CLOSE, 0, 0)


def close(title: str):
    """Close a window
    """
    win_man = WindowManager()
    win_man.get_window_by_title(f".*?{title}.*?")
    win_man.close()


def minimize(title: str):
    """Minimize a window
    """
    win_man = WindowManager()
    win_man.get_window_by_title(f".*?{title}.*?")
    win_man.minimize()


def maximize(title: str):
    """Minimize a window
    """
    win_man = WindowManager()
    win_man.get_window_by_title(f".*?{title}.*?")
    win_man.maximize()


def restore(title: str):
    """Restore a window
    """
    win_man = WindowManager()
    win_man.get_window_by_title(f".*?{title}.*?")
    win_man.restore()


def focus(title: str):
    """Bring Focus to a window
    """
    win_man = WindowManager()
    win_man.get_window_by_title(f".*?{title}.*?")
    win_man.focus()


def open_app(app: str):
    """Open an application

    Args:
        app_path (str): path to the application
    """
    if isfile(app):
        Popen(app)
    else:
        try:
            system(f"start {app}")
        except Exception as err:
            raise Exception(f"Could not open {app} because of {err}") from err
