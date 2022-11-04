"""Python Automation using Mouse and Keyboard, for the masses
"""

# pylint: disable=unused-import
from time import sleep
from sys import exit as end

from os import remove
from os import startfile
from os.path import isfile
from os.path import sep

from pathlib import Path

from re import search
from re import match

from tkinter import Tk
from tkinter import Label
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
from pyautogui import alert
from pyautogui import click
from pyautogui import write
from pyautogui import keyUp
from pyautogui import keyDown
from pyautogui import linear
from pyautogui import center
from pyautogui import locate
from pyautogui import moveTo
from pyautogui import mouseUp
from pyautogui import confirm
from pyautogui import position
from pyautogui import mouseDown
from pyautogui import screenshot
from pyautogui import press as keys  # this normally is to be used for same key left, left, left
from pyautogui import hotkey as keys2  # this is best solution, pass list to be unpacked with *list
from pyautogui import locateOnScreen
from pyautogui import locateAllOnScreen
from pyautogui import scroll as scrollup
from pyautogui import hscroll as scrollright
from pyautogui import leftClick as leftclick
from pyautogui import rightClick as rightclick
from pyautogui import middleClick as middleclick
from pyautogui import doubleClick as doubleclick
from pyautogui import tripleClick as tripleclick
from keyboard import send as keys3  # works mostly on windows - TODO: Check difference to below
from keyboard import press_and_release as keys4  # works mostly on windows

from win32gui import FindWindow
from win32gui import EnumWindows
from win32gui import GetWindowText
from win32gui import SetForegroundWindow
from win32gui import GetForegroundWindow

from pytesseract import image_to_string

from screeninfo import get_monitors

# from cv2 import cv2
import cv2
from cv2 import imread
from numpy import where


# Image Extensions supported
# TODO: Check if all work
IMG_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".gif",
    ".pdf",
    ".webp",
    ".PNG",
    ".JPG",
    ".JPEG",
    ".TIFF",
    ".TIF",
    ".BMP",
    ".GIF",
    ".PDF",
    ".WEBP"
)

MOUSE_ACTIONS = (
    "click",
    "leftclick",
    "rightclick",
    "doubleclick",
    "tripleclick",
    "scrollup",
    "scrolldown",
    "scrollleft",
    "scrollright",
)

WAIT_ACTIONS = (
    "waitwhile",
    "waituntil",
)

KEYBOARD_ACTIONS = (
    "write",
    "pastetext",
    "keys",
    "keys2",
    "keys3",
    "keys4",
    "copy",
    "paste",
)

APPS_ACTIONS = (
    "startfile",
    "focus_word",
    "office_replace",
)

ALL_ACTIONS = MOUSE_ACTIONS + KEYBOARD_ACTIONS + WAIT_ACTIONS + APPS_ACTIONS


class AutoMonkeyNoAction(Exception):
    """
    AutoMonkey chain function will raise this Exception if no action exists
    in an automation step of the chain sequence.
    """
    def __init__(self, message):
        super().__init__(f"The provided action is not supported: {message}")


class AutoMonkeyNoTarget(Exception):
    """
    AutoMonkey chain function will raise this Exception if no target exists
    in an automation step of the chain sequence.
    """
    def __init__(self, message):
        super().__init__(f"The provided target is not supported: {message}")

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


def get_center(image: str):
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


def vertical_point(point, _):
    """Returns a PyAutoGUI point that is offset vertically
    Args:
        point (PyAutoGUI point): [A Tuple with an X and a Y]
        _ (int): The offset. Can be positive or negative.
                Positive = Above. Negative = Below
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset vertically.
    """
    return point[0], point[1] - _


def horizontal_point(point, _):
    """Returns a PyAutoGUI point that is offset horizontally
    Args:
        point (PyAutoGUI point): [A Tuple with an X and a Y]
        _ (int): The offset. Can be positive or negative.
                Positive = Right. Negative = Left
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset horizontally.
    """
    return point[0] + _, point[1]


def diagonal_point(point, x_point, y_point):
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


def copy_from_to(point1, point2):
    """This function will copy text from one point to another.
    Args:
        point1 (PyAutoGUI point): PyAutoGUI start point (from)
        point2 (PyAutoGUI point): PyAutoGUI end point (to)
    """

    mouseDown(point1)
    moveTo(point2)
    mouseUp()
    clear_clipboard()

    while paste() == '':
        keys('ctrl+c')

    copied = paste()
    clear_clipboard()
    return copied


def copy_from(point):
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
    keys("ctrl+a")
    sleep(0.2)

    while paste() == "":
        keys("ctrl+c")

    copied = paste()
    clear_clipboard()

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

class ShowCoordinates(Toplevel):
    def __init__(self):
        self.window = Tk()  # Toplevel()  # Tk()
        self.canvas = None

    def shoot(self):
        """Take the screenshot
        """
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        self.window.attributes('-fullscreen', True, '-alpha', 0.4)
        self.window.configure(bg='black')

        self.canvas = Canvas(
            self.window,
            width=self.window.winfo_screenwidth(),
            height=self.window.winfo_screenheight(),
            cursor="crosshair"
        )
        self.canvas.configure(highlightthickness=0, bg='black')
        self.canvas.pack()

        self.window.after(1, self._crosshair, None)
        self.window.mainloop()

    def _crosshair(self, coords):
        x_point, y_point = position()

        self.canvas.delete(coords)
        if coords is None:
            self.canvas.create_text(
                120,
                20,
                text=f"Press ESC to exit.",
                fill='red',
                font=("Helvetica", 20),
            )
        coords = self.canvas.create_text(
            x_point + 100 if x_point < size()[0] - 200 else x_point - 100,
            y_point if (y_point < 150 and x_point < 50) else y_point + 100,
            text=f"x={x_point}, y={y_point}",
            fill='red',
            font=("Helvetica", 14),
        )
        self.window.after(1, self._crosshair, coords)

def get_img_height(image_file):
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


def get_img_width(image_file):
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


def get_text_from_region(region) -> str:
    """Makes a screenshot of a screen region and performs OCR on it
    Args:
        region (PyAutoGUI region): Left, Top, Width, Height
    Returns:
        str: The text from the region
    """

    snap = screenshot(region=region)
    snap.save("temp.jpg")
    sleep(1)
    img = imread('temp.jpg')

    custom_config = r'--oem 3 --psm 6'
    text = image_to_string(img, config=custom_config)
    remove('temp.jpg')
    return text


def count_needles(needle: str, haystack: str) -> int:
    """Counts how many times an image appears in a bigger image

    Args:
        needle (str): image filename to be counted
        haystack (str): filename of image in which to search

    Returns:
        int: Count of occurrences of needle in the haystack
    """

    needle = __add_ext(needle)
    haystack = __add_ext(haystack)

    hay = imread(haystack)
    need = imread(needle)

    res = cv2.cv2.matchTemplate(hay, need, cv2.cv2.TM_CCOEFF_NORMED)

    threshold = .9  # 9 is more precise. 8 gives some false positives
    loc = where(res >= threshold)

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
    keys('ctrl+v')
    sleep(0.1)
    copy(temp_clipboard)


def scrolldown(clicks: int):
    """Scroll down a given number of clicks

    Args:
        clicks (int): number of clicks
    """
    scrollup(-clicks)

def scrollleft(clicks):
    """Scroll left a given number of clicks

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
    keys('ctrl+h')
    sleep(0.2)
    keys('alt+n')
    sleep(0.2)
    keys('ctrl+v')
    sleep(0.2)
    copy(with_this)
    sleep(0.2)
    keys('alt+i')
    sleep(0.2)
    keys('ctrl+v')
    sleep(0.2)
    keys('ctrl+v')
    sleep(0.2)
    keys('alt+a')
    sleep(0.2)
    keys('enter')
    sleep(0.2 * delay_factor)
    keys('enter')
    sleep(0.2 * delay_factor)
    keys('esc')
    sleep(0.2)
    keys('esc')
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
        if match(pattern, str(GetWindowText(hwnd))) is not None:
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
        keyUp('alt')


def focus_word(title):
    """Bring Focus to an opened Word document
    """
    title = title if (not title.endswith('.docx')
                      and not title.endswith('.doc')
                      and not title.endswith('.docm'))\
        else title.replace('.docx', '')\
                  .replace('.docm', '')\
                  .replace('.doc', '')
    win_man = WindowManager()
    win_man.get_window_by_title(f"{title} - Word")
    win_man.focus()


def chain(*steps: dict, debug=False):
    """Chain together a series of automation steps

    Args:
        *steps (dict): Unlimitted number of automation steps as dictionaries.
        Each automation step should be a dictionary with 1 or more pairs:
            - First pair is the Action - Target pair. The only mandatory pair.
              Example: dict(click: "image.jpg") or {"click": "image.jpg"}
            - Next possible pairs are optional:
                * wait - Seconds to wait after performing the action. Defaults to zero.
                * confidence - optional. Used only for actions on images. Confidence on locating the image.
                  Defaults to 0.9
                *

        Example of steps:
            chain(
                dict(write="this string", wait=0.5),
                dict(write="this other string"),
                dict(click="C:\\Folder1\\Folder2\\image.jpg", wait=2, confidence=0.8),
                debug=True)

        debug (bool, optional): Debug variable, if True will print each step. Defaults to False.
    """
    monitors = {}
    mon_list = [(mon.x, mon.y) for mon in get_monitors()]
    mon_list = sorted(mon_list, key=lambda tup: tup[0])
    for ind, mon in enumerate(mon_list):
        monitors[ind] = (mon[0], mon[1])

    for step in steps:
        action = None
        target = None
        for arg_pair in step.items():
            action = arg_pair[0] if arg_pair[0] in ALL_ACTIONS else action
            target = arg_pair[1] if arg_pair[0] in ALL_ACTIONS else target
            skip = bool(arg_pair[1]) if arg_pair[0] == 'skip' else False
            wait = float(arg_pair[1]) if arg_pair[0] == 'wait' else 0
            confidence = float(arg_pair[1]) if arg_pair[0] == 'confidence' else 0.9
            v_offset = int(arg_pair[1]) if arg_pair[0] == 'v_offset' else 0
            h_offset = int(arg_pair[1]) if arg_pair[0] == 'h_offset' else 0
            offset = str(arg_pair[1]) if arg_pair[0] == 'offset' else None
            monitor = arg_pair[1] if arg_pair[0] == 'monitor' else 1

        if action not in ALL_ACTIONS:
            raise AutoMonkeyNoAction(action)

        if target is None:
            raise AutoMonkeyNoTarget(target)

        if debug:
            print(step)

        target = target.split("+") if action in ("keys", "keys2") else target  # keys is from pyautogui import press. Ex: pyautogui.press(['left', 'left', 'left'])
        try:
            target = (target[0] + monitors[monitor - 1][0], target[1]) if isinstance(target, tuple) and target[0] < monitors[1][0] else target
        except IndexError:
            pass
        except KeyError:
            pass

        if action in MOUSE_ACTIONS and not isinstance(target, tuple) and not isinstance(target, int):
            slept = 0
            target = __add_ext(target)

            # Wait until next target comes into view
            while not is_on_screen(target) and not skip:
                sleep(0.1)
                slept += 0.1
                if int(slept) == 30:  # For production make it 300
                    stop = confirm("Next target was not found for 5 minutes.\
                                    Would you like to continue or stop?",
                                   "Continue?",
                                   ["Continue", "Stop"]
                                   )
                    if stop == "Stop":
                        end()

            bullseye = locateOnScreen(target, confidence=confidence)
            bullseye = get_center(bullseye)
            bullseye = diagonal_point(bullseye, h_offset, v_offset)
            if offset != "" and offset is not None:
                globals()["__offset_clicks"](bullseye, target, offset, action)
            else:
                globals()[action](bullseye)
        else:
            # Keyboard Actions
            # Wait Actions
            # Apps Actions
            # Mouse Actions with point given as tuple
            if target == "keys2":
                globals()[action](*target)
            else:
                globals()[action](target)

        sleep(wait)
