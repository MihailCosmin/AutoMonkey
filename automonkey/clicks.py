"""A series of clikc with offsets
"""
from pyautogui import click
from pyautogui import rightClick
from pyautogui import doubleClick
from pyautogui import tripleClick

import automonkey.get_img_height as get_img_height
import automonkey.horizontal_point as horizontal_point


def northClick(point, img: str):
    """Click above (to the north) with an offset
    equal to the height of the image given.

    Args:
        point ([type]): center point of the image
        img (str): image location + filename
    """
    click(horizontal_point(point, get_img_height(img)))


def northRightClick(point, img: str):
    """Click above (to the north) with an offset
    equal to the height of the image given.

    Args:
        point ([type]): center point of the image
        img (str): image location + filename
    """
    rightClick(horizontal_point(point, get_img_height(img)))


def northDoubleClick(point, img: str):
    """DoubleClick above (to the north) with an offset
    equal to the height of the image given.

    Args:
        point ([type]): center point of the image
        img (str): image location + filename
    """
    doubleClick(horizontal_point(point, get_img_height(img)))

def northTripleClick(point, img: str):
    """TripleClick above (to the north) with an offset
    equal to the height of the image given.

    Args:
        point ([type]): center point of the image
        img (str): image location + filename
    """
    tripleClick(horizontal_point(point, get_img_height(img)))
