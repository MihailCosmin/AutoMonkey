"""Python Automation using Mouse and Keyboard for the masses
"""

from time import sleep
from sys import exit as finish

from os import remove
from os.path import isfile
from re import findall

from clipboard import paste
from clipboard import copy as clipboardcopy

try:
    from PIL import Image
except ImportError:
    import Image

from pyautogui import alert
from pyautogui import click
from pyautogui import write
from pyautogui import scroll
from pyautogui import center
from pyautogui import locate
from pyautogui import moveTo
from pyautogui import mouseUp
from pyautogui import confirm
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

def get_center(image: str) -> point:
    """[summary]
    Args:
        image ([str]): [image to be located]
    Returns:
        [point]: [Returns the center of the located image as a point or None]
    """

    try:
        if image is not None:
            if image.lower().endswith(('.png',
                                       '.jpg',
                                       '.jpeg',
                                       '.tiff',
                                       '.tif',
                                       '.bmp',
                                       '.gif')):
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.png"):
                image = f"{image}.png"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.jpg"):
                image = f"{image}.jpg"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.jpeg"):
                image = f"{image}.jpeg"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.tiff"):
                image = f"{image}.tiff"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.tif"):
                image = f"{image}.tif"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.bmp"):
                image = f"{image}.bmp"
                located_image = locateOnScreen(image, confidence=0.9)
            elif isfile(f"{image}.gif"):
                image = f"{image}.gif"
                located_image = locateOnScreen(image, confidence=0.9)
            else:
                return None
            ctr = center(located_image)
            return ctr
    except TypeError:
        return None
    except NameError:
        return None
