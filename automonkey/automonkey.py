"""Python Automation using Mouse and Keyboard for the masses
"""

from time import sleep
from sys import exit as finish

from os import remove
from os.path import isfile

from clipboard import paste
from clipboard import copy as clipboardcopy

try:
    from PIL import Image
except ImportError:
    import Image

from pyautogui import alert
from pyautogui import click as click_
from pyautogui import write as write_
from pyautogui import scroll
from pyautogui import center
from pyautogui import locate
from pyautogui import moveTo
from pyautogui import mouseUp
from pyautogui import confirm
from pyautogui import position
from pyautogui import mouseDown
from pyautogui import screenshot
from pyautogui import rightClick
from pyautogui import doubleClick
from pyautogui import tripleClick
from pyautogui import locateOnScreen
from pyautogui import locateAllOnScreen
from keyboard import press_and_release as keys

from pytesseract import image_to_string

from cv2 import cv2
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


IMG_ACTIONS = ["click",
               "leftClick",
               "rightClick",
               "doubleClick",
               "tripleClick"
               ]

class AutoMonkeyNoAction(Exception):
    """
    AutoMonkey chain function will raise this Exception if no action exists
    in an automation step of the chain sequence.
    """


class AutoMonkeyNoTarget(Exception):
    """
    AutoMonkey chain function will raise this Exception if no target exists
    in an automation step of the chain sequence.
    """


def add_ext(filename: str) -> str:
    """Adds extension to an image filename if missing

    Args:
        filename (str): image filename (with or without extension)

    Returns:
        str: image filename with extension if was missing
    """

    for ext in IMG_EXT:
        if isfile(f"{filename}{ext}"):
            filename = f"{filename}{ext}"

    return filename


def is_on_screen(what: str) -> bool:
    """Checks whether an image is found on screen
    Args:
        what (str): image to locate on screen
    Returns:
        bool: Returns True if image is found and False if not.
    """

    found = False
    what = add_ext(what)

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

    image = add_ext(image)

    try:
        if str(type(image)) != '<class \'pyscreeze.Box\'>':
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
                Positive = Below. Negative = Above
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset vertically.
    """
    return point[0], point[1] + _


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
        x_point (int): The offset. Can be positive or negative.
                Positive = Below. Negative = Above
        y_point (int): The offset. Can be positive or negative.
                Positive = Right. Negative = Left
    Returns:
        [PyAutoGUI point]: The PyAutoGUI point offset diagonally.
    """
    return point[0] + x_point, point[1] + y_point


def clear_clipboard():
    """Try to clear the clipboard by copying an empty string
    Might not work in all cases, for example: in environments
    with shared/multiple clipboards.
    """
    for _ in range(0, 10):
        clipboardcopy("")


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

    while paste() == "":
        keys("ctrl+c")

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
    click_(point)
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


def get_img_height(image_file):
    """Function that returns the height of an image.
    Args:
        image_file (path): path to an image file, including filename.
    Returns:
        int: Height of the image
    """

    image_file = add_ext(image_file)

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

    image_file = add_ext(image_file)

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

    # Adding custom options
    custom_config = r'--oem 3 --psm 6'
    text = image_to_string(img, config=custom_config)
    remove('temp.jpg')
    return text


def get_subimg_count(needle: str, haystack: str) -> int:
    """Counts how many times an image appears in a bigger image

    Args:
        needle (str): image filename to be counted
        haystack (str): filename of image in which to search

    Returns:
        int: Count of occurrences of needle in the haystack
    """

    needle = add_ext(needle)
    haystack = add_ext(haystack)

    hay = cv2.imread(haystack)
    need = cv2.imread(needle)

    res = cv2.matchTemplate(hay, need, cv2.TM_CCOEFF_NORMED)

    threshold = .9  # 9 is more precise. 8 gives some false positives
    loc = where(res >= threshold)

    return len(loc[0])


def offset_clicks(point: tuple, img: str, offset_value: str, click_type: str):
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
        globals()[click_type](int(vertical_point(point, get_img_height(img))))
    if offset_value == "bellow":
        globals()[click_type](vertical_point(point, 0 - get_img_height(img)))
    if offset_value == "right":
        globals()[click_type](horizontal_point(point, get_img_width(img)))
    if offset_value == "left":
        globals()[click_type](horizontal_point(point, 0 - get_img_width(img)))


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
                dict(click="C:\\Desktop\\image.jpg", wait=2, confidence=0.8),
                debug=True)

        debug (bool, optional): Debug variable, if True will print each step. Defaults to False.
    """

    list_of_actions = [
        "click",
        "leftClick",
        "rightClick",
        "doubleClick",
        "tripleClick",
        "write",
        "pasteWrite",
        "type",
        "copy",
        "paste",
        "waitWhile",
        "waitUntil",
    ]

    for step in steps:
        action = ""
        target = ""
        skip = False
        wait = 0
        confidence = 0.9
        v_offset = 0
        h_offset = 0
        offset = ""
        for arg_pair in step.items():
            action = arg_pair[0] if arg_pair[0] in list_of_actions else action
            target = arg_pair[1] if arg_pair[0] in list_of_actions else target

            skip = bool(arg_pair[1]) if arg_pair[0] == 'skip' else skip
            wait = float(arg_pair[1]) if arg_pair[0] == 'wait' else wait
            confidence = float(arg_pair[1]) if arg_pair[0] == 'confidence' else confidence
            v_offset = int(arg_pair[1]) if arg_pair[0] == 'v_offset' else v_offset
            h_offset = int(arg_pair[1]) if arg_pair[0] == 'h_offset' else h_offset
            offset = str(arg_pair[1]) if arg_pair[0] == 'offset' else offset

        if debug:
            print(step)

        # Wait until next target comes into view
        # If this works correctly there should be no need for
        # custom specified wait times

        if action in IMG_ACTIONS:
            slept = 0
            target = add_ext(target)

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
                        finish()

            bullseye = locateOnScreen(target, confidence=confidence)
            bullseye = get_center(bullseye)
            bullseye = diagonal_point(bullseye, h_offset, v_offset)
            if offset != "":
                globals()["offset_clicks"](bullseye, target, offset, action)
            else:
                globals()[action](bullseye)

        sleep(wait)
