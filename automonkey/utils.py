from time import sleep

from clipboard import copy as copy1
from pyperclip import copy as copy2

from clipboard import paste

from pyautogui import click
from pyautogui import moveTo
from pyautogui import mouseUp
from pyautogui import mouseDown
from pyautogui import scroll as scrollup
from pyautogui import hscroll as scrollright
from pyautogui import hotkey as keys2  # this is best solution, pass list to be unpacked with *list

from .img_funcs import is_on_screen

def copy(text: str):
    """Copy text to clipboard using two functions

    Args:
        text (str): text to be copied to clipboard
    """
    copy1(text)
    copy2(text)


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
