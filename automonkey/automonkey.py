"""Python Automation using Mouse and Keyboard, for the masses
"""

from time import sleep
from sys import exit as end

from os import remove
from os import startfile  # It is used
from os import system
from os.path import isfile

from subprocess import Popen

from re import search

from tkinter import Tk
from tkinter import Canvas
from tkinter import Toplevel

from clipboard import paste
from clipboard import copy as copy1
from pyperclip import copy as copy2

try:
    from PIL import Image
except ImportError:
    import Image

from pyscreeze import Box

from pyautogui import size
from pyautogui import click
from pyautogui import write  # It is used
from pyautogui import keyUp
from pyautogui import keyDown
from pyautogui import center
from pyautogui import moveTo
from pyautogui import mouseUp
from pyautogui import confirm
from pyautogui import position
from pyautogui import mouseDown
from pyautogui import screenshot
from pyautogui import press as keys  # this normally is to be used for same key left, left, left
from pyautogui import hotkey as keys2  # this is best solution, pass list to be unpacked with *list
from pyautogui import locateOnScreen
from pyautogui import scroll as scrollup
from pyautogui import hscroll as scrollright
from pyautogui import leftClick as leftclick  # It is used
from pyautogui import rightClick as rightclick  # It is used
from pyautogui import middleClick as middleclick  # It is used
from pyautogui import doubleClick as doubleclick  # It is used
from pyautogui import tripleClick as tripleclick  # It is used
from keyboard import send as keys3  # works mostly on windows - TODO: Check difference to below
from keyboard import press_and_release as keys4  # works mostly on windows

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

from pytesseract import image_to_string

from screeninfo import get_monitors

import cv2
from cv2 import imread
from numpy import where

if __name__ == "__main__":
    from constants import IMG_EXT
    from constants import MOUSE_ACTIONS
    from constants import WAIT_ACTIONS
    from constants import KEYBOARD_ACTIONS
    from constants import APPS_ACTIONS
    from constants import IMG_ACTIONS
    from constants import COMMON_APPS

    from exceptions import AutoMonkeyNoAction
    from exceptions import AutoMonkeyNoTarget
else:
    from .constants import IMG_EXT
    from .constants import MOUSE_ACTIONS
    from .constants import WAIT_ACTIONS
    from .constants import KEYBOARD_ACTIONS
    from .constants import APPS_ACTIONS
    from .constants import IMG_ACTIONS
    from .constants import COMMON_APPS

    from .exceptions import AutoMonkeyNoAction
    from .exceptions import AutoMonkeyNoTarget


ALL_ACTIONS = MOUSE_ACTIONS + KEYBOARD_ACTIONS + WAIT_ACTIONS + APPS_ACTIONS + IMG_ACTIONS

def __add_ext(filename: str) -> str:
    """Adds extension to an image filename if missing

    Args:
        filename (str): image filename (with or without extension)

    Returns:
        str: image filename with extension if was missing
    """

    for ext in IMG_EXT:
        if isfile(f"{filename}{ext}"):
            return f"{filename}{ext}"
    return filename


def is_on_screen(what: str) -> bool:
    """Checks whether an image is found on screen
    Args:
        what (str): image to locate on screen
    Returns:
        bool: Returns True if image is found and False if not.
    """

    found = False
    what = __add_ext(what)

    if locateOnScreen(what, confidence=0.9) is not None:
        found = True

    return found


def get_center(image: str) -> tuple:
    """Find the center of an image on screen
    Args:
        image ([str]): image to be located
    Returns:
        [point]: Returns the center of the located image as a point or None
    """

    image = __add_ext(image)

    try:
        if not isinstance(image, Box):
            return center(locateOnScreen(image, confidence=0.9))
        return center(image)
    except TypeError:
        return None
    except NameError:
        return None


def vertical_point(point, offset) -> tuple:
    """Returns a PyAutoGUI point that is offset vertically
    Args:
        point (PyAutoGUI point): [A Tuple with an X and a Y]
        offset (int): The offset. Can be positive or negative.
                Positive = Above. Negative = Below
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset vertically.
    """
    return point[0], point[1] - offset


def horizontal_point(point, offset) -> tuple:
    """Returns a PyAutoGUI point that is offset horizontally
    Args:
        point (PyAutoGUI point): [A Tuple with an X and a Y]
        offset (int): The offset. Can be positive or negative.
                Positive = Right. Negative = Left
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset horizontally.
    """
    return point[0] + offset, point[1]


def diagonal_point(point, x_point, y_point) -> tuple:
    """Returns a PyAutoGUI point that is offset diagonally
    Args:
        point (PyAutoGUI point): [A Tuple with an X and a Y]
        x_point (int): The horizontal offset. Can be positive or negative.
                Positive = Right. Negative = Left
        y_point (int): The vertical offset. Can be positive or negative.
                Positive = Above. Negative = Below
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset diagonally.
    """
    return point[0] + x_point, point[1] - y_point


def clear_clipboard():
    """Try to clear the clipboard by copying an empty string
    Might not work in all cases, for example: in environments
    with shared/multiple clipboards.
    """
    for _ in range(0, 10):
        copy('')


def copy_from_to(*args) -> str:
    """This function will copy text from one point to another.
    Args:
        point1 (PyAutoGUI point): PyAutoGUI start point (from)
        point2 (PyAutoGUI point): PyAutoGUI end point (to)

    Returns:
        str: The copied text
    """
    if len(args) == 1:
        assert isinstance(args[0][0], tuple), "The argument must be a tuple. First point tuple"
        assert isinstance(args[0][1], tuple), "The argument must be a tuple. Second point tuple"
        assert isinstance(args[0][0][0], int), "The argument must be an integer. First point X"
        assert isinstance(args[0][0][1], int), "The argument must be an integer. First point Y"
        assert isinstance(args[0][1][0], int), "The argument must be an integer. Second point X"
        assert isinstance(args[0][1][1], int), "The argument must be an integer. Second point Y"
        point1 = (args[0][0][0], args[0][0][1])
        point2 = (args[0][1][0], args[0][1][1])
    elif len(args) == 2:
        assert isinstance(args[0], tuple), "The argument must be a tuple. First point tuple"
        assert isinstance(args[1], tuple), "The argument must be a tuple. Second point tuple"
        assert isinstance(args[0][0], int), "The argument must be an integer. First point X"
        assert isinstance(args[0][1], int), "The argument must be an integer. First point Y"
        assert isinstance(args[1][0], int), "The argument must be an integer. Second point X"
        assert isinstance(args[1][1], int), "The argument must be an integer. Second point Y"
        point1 = args[0]
        point2 = args[1]

    mouseDown(point1)
    moveTo(point2)
    mouseUp()
    clear_clipboard()

    while str(paste()) == '':
        keys2('ctrl', 'c')

    copied = paste()
    print(copied)
    copy(copied)
    return copied


def copy_from(point) -> str:
    """This function will copy text from one point to the end of line.
    This function uses select all functionality (ctrl+a) and as such
    it should be used only when you are sure ctrl+a will select only
    the content you want.
    Args:
        point (PyAutoGUI point): PyAutoGUI start point (from)
    Returns:
        [string]: The copied text.
    """

    clear_clipboard()
    click(point)
    sleep(0.2)
    keys2('ctrl', 'a')
    sleep(0.2)

    while str(paste()) == '':
        keys2('ctrl', 'c')

    copied = paste()
    copy(copied)

    return copied


def track_mouse():
    """Tracks the mouse position and when the mouse stops moving
    for 1 second it prints the position in the terminal
    """

    cur_pos = ""
    print("Tracking mouse position started")
    print("Press ctrl+c anytime to end tracking")
    try:
        while True:
            if cur_pos != position():
                cur_pos = position()
                print(position())
            sleep(1)
    except KeyboardInterrupt:
        print("Tracking mouse position stopped")


class PositionTracker:  # was Toplevel
    def __init__(self, follow_mouse: bool = False):
        self.follow_mouse = follow_mouse
        self.window = Tk()  # Was Tk()
        self.window.canvas = None
        self.coords = None

    def start(self, get_coords: bool = False):
        """Take the screenshot
        """
        # if get_coords:
        #     self.window.bind('<Control-Button-1>', lambda e: self.window.destroy())
        # else:
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        self.window.attributes('-fullscreen', True, '-alpha', 0.3)
        self.window.configure(bg='black')

        self.window.canvas = Canvas(
            self.window,
            width=self.window.winfo_screenwidth(),
            height=self.window.winfo_screenheight(),
            cursor="crosshair"
        )
        self.window.canvas.configure(highlightthickness=0, bg='black')
        self.window.canvas.pack()

        self.window.after(1, self._crosshair, None, get_coords)
        self.window.mainloop()
        if get_coords:
            return self.coords
        return None

    def _crosshair(self, coords, get_coords: bool = False):
        if get_coords:
            self.window.canvas.create_text(
                400,
                20,
                text="CTRL+Left Click to get the cursor coordinates",
                fill='red',
                font=("Helvetica", 30),
            )
            self.coords = position()
        else:
            x_point, y_point = position()

            self.window.canvas.delete(coords)
            if coords is None:
                self.window.canvas.create_text(
                    180,
                    20,
                    text="Press ESC to exit.",
                    fill='red',
                    font=("Helvetica", 30),
                )
            if self.follow_mouse:
                coords = self.window.canvas.create_text(
                    x_point + 100 if x_point < size()[0] - 200 else x_point - 100 if x_point < size()[0] + 100 else size()[0] / 2,
                    size()[1] / 2 if x_point > size()[0] + 100 else y_point + 100 if (y_point < 70 and x_point < 300) else y_point + 20 if y_point < size()[1] - 200 else y_point - 100,
                    text=f"x={x_point}, y={y_point}",
                    fill='red',
                    font=("Helvetica", 20) if x_point < size()[0] + 100 else ("Helvetica", 40),
                )
            else:
                coords = self.window.canvas.create_text(
                    size()[0] / 2,
                    size()[1] / 2,
                    text=f"x={x_point}, y={y_point}",
                    fill='red',
                    font=("Helvetica", 40),
                )
        self.window.after(1, self._crosshair, coords, get_coords)


def get_img_height(image_file: str) -> int:
    """Function that returns the height of an image.
    Args:
        image_file (path): path to an image file, including filename.
    Returns:
        int: Height of the image
    """

    image_file = __add_ext(image_file)

    img = Image.open(image_file)
    _, height = img.size

    return height


def get_img_width(image_file: str) -> int:
    """Function that returns the width of an image.
    Args:
        image_file (path): path to an image file, including filename.
    Returns:
        int: Width of the image
    """

    image_file = __add_ext(image_file)

    img = Image.open(image_file)
    width, _ = img.size

    return width


def get_text_from_region(*args) -> str:
    """Makes a screenshot of a screen region and performs OCR on it
    Args:
        Top left corner X, top left corner Y, bottom right corner X, bottom right corner Y
        or
        Top point (Tuple): (x, y) and Bottom point (Tuple): (x, y)
        or
        region (Tuple or PyAutoGUI region): (Left, Top, Width, Height)
        or
        Left (int), Top (int), Width (int), Height (int)
    Returns:
        str: The text from the region
    """
    if len(args) == 1:
        assert isinstance(args[0], tuple), "The argument must be a tuple of 4 integers: Left, Top, Width, Height"
        if len(args[0]) == 4:
            region = (args[0][0], args[0][1], args[0][2] - args[0][0], args[0][3] - args[0][1])
        elif len(args[0]) == 2:
            if args[0][1][1] > args[0][0][0] and args[0][1][1] > args[0][0][1]:
                region = (args[0][0][0], args[0][0][1], args[0][1][0] - args[0][0][0], args[0][1][1] - args[0][0][1])
            else:
                region = (args[0][0][0], args[0][0][1], args[0][1][0], args[0][1][1])
        else:
            region = args[0]
    elif len(args) == 2:
        assert isinstance(args[0], tuple), "The first argument must be a tuple of 2 integers: X, Y coordinates of the top left corner"
        assert isinstance(args[1], tuple), "The second argument must be a tuple of 2 integers: X, Y coordinates of the bottom right corner"
        region = (args[0][0], args[0][1], args[1][0] - args[0][0], args[1][1] - args[0][1])
    elif len(args) == 4:
        assert isinstance(args[0], int), "The first argument must be an integer: X coordinate of the top left corner"
        assert isinstance(args[1], int), "The second argument must be an integer: Y coordinate of the top left corner"
        assert isinstance(args[2], int), "The third argument must be an integer: Width of the region"
        assert isinstance(args[3], int), "The fourth argument must be an integer: Height of the region"
        if args[2] > args[0] and args[3] > args[1]:
            region = (args[0], args[1], args[2] - args[0], args[3] - args[1])
        else:
            region = (args[0], args[1], args[2], args[3])

    snap = screenshot(region=region)
    snap.save("temp.jpg")
    sleep(1)
    img = imread('temp.jpg')

    custom_config = r'--oem 3 --psm 6'
    text = image_to_string(img, config=custom_config)
    remove('temp.jpg')

    copy(text)  # in order to make the text available in the clipboard
    return text


def count_img(needle: str, haystack: str = None) -> int:
    """Counts how many times an image appears in a bigger image

    Args:
        needle (str): image filename to be counted
        haystack (str): filename of image in which to search

    Returns:
        int: Count of occurrences of needle in the haystack
    """

    needle = __add_ext(needle)
    if haystack:
        haystack = __add_ext(haystack)
        hay = imread(haystack)
    else:
        haystack = screenshot("temp.jpg")
        hay = imread("temp.jpg")
        remove("temp.jpg")

    need = imread(needle)

    res = cv2.cv2.matchTemplate(hay, need, cv2.cv2.TM_CCOEFF_NORMED)

    threshold = .9  # 9 is more precise. 8 gives some false positives
    loc = where(res >= threshold)

    copy(len(loc[0]))  # in order to make the text available in the clipboard
    return len(loc[0])


def __offset_clicks(point: tuple, img: str, offset_value: str, click_type: str):
    """Offset Clicks

    Args:
        point (tuple): PyAutoGUI Point as a (x, y) tuple
        img (str): image path that was the source of the point
        offset_value (str): Offset type:
                                         - above
                                         - bellow
                                         - right
                                         - left
                                         - upper-left
                                         - upper-right
                                         - lower-left
                                         - lower-right
        click_type (str): click, rightClick, doubleClcik, etc
    """
    if offset_value == "above":
        globals()[click_type](vertical_point(point, get_img_height(img)))
    if offset_value == "bellow":
        globals()[click_type](vertical_point(point, 0 - get_img_height(img)))
    if offset_value == "right":
        globals()[click_type](horizontal_point(point, get_img_width(img)))
    if offset_value == "left":
        globals()[click_type](horizontal_point(point, 0 - get_img_width(img)))
    if offset_value == "upper-left":
        globals()[click_type](diagonal_point(point, 0 - get_img_width(img), get_img_height(img)))
    if offset_value == "upper-right":
        globals()[click_type](diagonal_point(point, get_img_width(img), get_img_height(img)))
    if offset_value == "lower-left":
        globals()[click_type](diagonal_point(point, 0 - get_img_width(img), 0 - get_img_height(img)))
    if offset_value == "lower-right":
        globals()[click_type](diagonal_point(point, get_img_width(img), 0 - get_img_height(img)))


def copy(text: str):
    """Copy text to clipboard using two functions

    Args:
        text (str): text to be copied to clipboard
    """
    copy1(text)
    copy2(text)


def pastetext(text: str):
    """Copy the text and paste it in the applicable place
    This type of text output can be used when write or type are not capable
    of writting special characters. For example German or Chinese characters.
    In those cases a simple solution would be to copy the text and just paste it in the
    where needed.

    Args:
        text (str): text to be output
    """

    temp_clipboard = paste()
    while paste() != text:
        copy(text)
    keys2('ctrl', 'v')
    copy(temp_clipboard)


def scrolldown(clicks: int):
    """Scroll down a given number of clicks
    Note: You have to select the scrollable area first

    Args:
        clicks (int): number of clicks
    """
    scrollup(-clicks)


def scrollleft(clicks: int):
    """Scroll left a given number of clicks
    Note: You have to select the scrollable area first

    Args:
        clicks (int): number of clicks
    """
    scrollright(-clicks)


def waitwhile(img: str):
    """While an image is on screen wait
    For example a loading window.

    Args:
        img (str): image location path + name
    """

    while is_on_screen(img):
        sleep(0.1)


def waituntil(img: str):
    """Wait until an image appears on screen
    For example wait for a software to start

    Args:
        img (str): image location path + name
    """

    while not is_on_screen(img):
        sleep(0.1)


def msoffice_replace(replace_this: str, with_this: str, delay_factor: float = 1):
    """Search and replace in all MS Office Software. No Guarantees.

    Args:
        replace_this (str): string to be replaced
        with_this (str): new string
        delay_factor (float, optional): Delay factor in case
            the default sleep times for waiting that the replacement
            is finished are too fast. Defaults to 1.
    """
    copy(replace_this)
    sleep(0.2)
    keys2('ctrl', 'h')
    sleep(0.2)
    keys2('alt', 'n')
    sleep(0.2)
    keys2('ctrl', 'v')
    sleep(0.2)
    copy(with_this)
    sleep(0.2)
    keys2('alt', 'i')
    sleep(0.2)
    keys2('ctrl', 'v')
    sleep(0.2)
    keys2('alt', 'a')
    sleep(0.2)
    keys2('enter')
    sleep(0.2 * delay_factor)
    keys2('enter')
    sleep(0.2 * delay_factor)
    keys2('esc')
    sleep(0.2)
    keys2('esc')
    sleep(0.2)


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

def __wait_for_target(target: any, skip: bool = False):
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


def __prepare_step(raw_step: dict) -> dict:
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

    # TODO: To have a function that can be called with different number and different types of arguments look into function overloading
    # https://stackoverflow.com/questions/6434482/python-function-overloading
    # This could be needed for:
    # 1. get_text_from_region
    # 2. copy_from_to

    monitors = {}
    for _, mon in enumerate(sorted([(mon.x, mon.y) for mon in get_monitors()], key=lambda tup: tup[0])):
        monitors[_] = (mon[0], mon[1])

    for _ in steps:
        step = __prepare_step(_)

        if debug:
            print(_)

        step["target"] = step["target"].split("+") if step["action"] in ("keys", "keys2") else step["target"]
        try:
            if step["action"] in ("keys", "keys2") and isinstance(step["target"], tuple):
                step["target"] = (step["target"][0] + monitors[step["monitor"] - 1][0], step["target"][1]) if step["target"][0] < monitors[1][0] else step["target"]
        except IndexError:
            pass
        except KeyError:
            pass

        if step["action"] in MOUSE_ACTIONS and not isinstance(step["target"], tuple) and not isinstance(step["target"], int):
            step["target"] = __add_ext(step["target"])
            __wait_for_target(step["target"], step["skip"])

            bullseye = locateOnScreen(step["target"], confidence=step["confidence"])
            bullseye = get_center(bullseye)
            bullseye = diagonal_point(bullseye, step["h_offset"], step["v_offset"])
            if step["offset"] not in ("", None):
                globals()["__offset_clicks"](bullseye, step["target"], step["offset"], step["action"])
            else:
                globals()[step["action"]](bullseye)
        else:
            if step["action"] in ("keys2", "msoffice_replace"):
                globals()[step["action"]](*step["target"])
            elif step["action"] == "paste":
                pastetext(paste())
            elif step["action"] == "open_app":
                if step["target"].lower() in COMMON_APPS:
                    globals()[step["action"]](COMMON_APPS[step["target"].lower()])
                else:
                    globals()[step["action"]](step["target"])
            else:
                globals()[step["action"]](step["target"])

        sleep(step["wait"])


if __name__ == "__main__":
    tracker = PositionTracker()
    print(tracker.start(True))