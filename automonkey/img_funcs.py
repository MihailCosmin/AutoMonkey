from os import remove
from os.path import isfile

from time import sleep

from pyautogui import center
from pyautogui import locateOnScreen

from pyscreeze import Box
from pytesseract import image_to_string

from clipboard import copy as copy1
from pyperclip import copy as copy2

try:
    from PIL import Image
except ImportError:
    import Image

import cv2
from cv2 import imread
from numpy import where

from pyautogui import screenshot

from .constants import IMG_EXT

# TODO: Add mousedown, mouseup, drag, and drop functions

def copy(text: str):
    """Copy text to clipboard using two functions

    Args:
        text (str): text to be copied to clipboard
    """
    copy1(text)
    copy2(text)

def _add_ext(filename: str) -> str:
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
    what = _add_ext(what)

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

    image = _add_ext(image)

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

def get_img_height(image_file: str) -> int:
    """Function that returns the height of an image.
    Args:
        image_file (path): path to an image file, including filename.
    Returns:
        int: Height of the image
    """

    image_file = _add_ext(image_file)

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

    image_file = _add_ext(image_file)

    img = Image.open(image_file)
    width, _ = img.size

    return width

def __transform_region_1(*args) -> tuple:
    assert isinstance(args[0], tuple), "The argument must be a tuple of 4 integers: Left, Top, Width, Height"
    if len(args[0]) == 4:
        region = (args[0][0], args[0][1], args[0][2] - args[0][0], args[0][3] - args[0][1])
    elif len(args[0]) == 2:
        region = __transform_region_4(args)
    else:
        region = args[0]
    return region

# TODO: To have a function that can be called with different number and different types of arguments look into function overloading
# https://stackoverflow.com/questions/6434482/python-function-overloading
# This could be needed for:
# 1. get_text_from_region
# 2. copy_from_to

def __transform_region_2(*args) -> tuple:
    assert isinstance(args[0], tuple), "The first argument must be a tuple of 2 integers: X, Y coordinates of the top left corner"
    assert isinstance(args[1], tuple), "The second argument must be a tuple of 2 integers: X, Y coordinates of the bottom right corner"
    return (args[0][0], args[0][1], args[1][0] - args[0][0], args[1][1] - args[0][1])

def __transform_region_3(*args) -> tuple:
    assert isinstance(args[0], int), "The first argument must be an integer: X coordinate of the top left corner"
    assert isinstance(args[1], int), "The second argument must be an integer: Y coordinate of the top left corner"
    assert isinstance(args[2], int), "The third argument must be an integer: Width of the region"
    assert isinstance(args[3], int), "The fourth argument must be an integer: Height of the region"
    if args[2] > args[0] and args[3] > args[1]:
        region = (args[0], args[1], args[2] - args[0], args[3] - args[1])
    else:
        region = (args[0], args[1], args[2], args[3])
    return region

def __transform_region_4(*args) -> tuple:
    if args[0][1][1] > args[0][0][0] and args[0][1][1] > args[0][0][1]:
        region = (args[0][0][0], args[0][0][1], args[0][1][0] - args[0][0][0], args[0][1][1] - args[0][0][1])
    else:
        region = (args[0][0][0], args[0][0][1], args[0][1][0], args[0][1][1])
    return region

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
        region = __transform_region_1(args)
    elif len(args) == 2:
        region = __transform_region_2(args)
    elif len(args) == 4:
        region = __transform_region_3(args)

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

    needle = _add_ext(needle)
    if haystack:
        haystack = _add_ext(haystack)
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


def _offset_clicks(point: tuple, img: str, offset_value: str, click_type: str):
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
        click_type (str): click, rightClick, doubleClick, etc
    """
    __offset_clicks_1(point, img, offset_value, click_type)
    __offset_clicks_2(point, img, offset_value, click_type)

def __offset_clicks_1(point: tuple, img: str, offset_value: str, click_type: str):
    if offset_value == "above":
        globals()[click_type](vertical_point(point, get_img_height(img)))
    if offset_value == "bellow":
        globals()[click_type](vertical_point(point, 0 - get_img_height(img)))
    if offset_value == "right":
        globals()[click_type](horizontal_point(point, get_img_width(img)))
    if offset_value == "left":
        globals()[click_type](horizontal_point(point, 0 - get_img_width(img)))

def __offset_clicks_2(point: tuple, img: str, offset_value: str, click_type: str):
    if offset_value == "upper-left":
        globals()[click_type](diagonal_point(point, 0 - get_img_width(img), get_img_height(img)))
    if offset_value == "upper-right":
        globals()[click_type](diagonal_point(point, get_img_width(img), get_img_height(img)))
    if offset_value == "lower-left":
        globals()[click_type](diagonal_point(point, 0 - get_img_width(img), 0 - get_img_height(img)))
    if offset_value == "lower-right":
        globals()[click_type](diagonal_point(point, get_img_width(img), 0 - get_img_height(img)))