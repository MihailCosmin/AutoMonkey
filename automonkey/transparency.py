from win32gui import FindWindow
from win32gui import SetWindowLong
from win32gui import GetWindowLong
from winxpgui import SetLayeredWindowAttributes
from win32con import GWL_EXSTYLE
from win32con import LWA_ALPHA
from win32con import WS_EX_LAYERED
from win32api import RGB

def transparent_window(w_name: str):
    """Make a window transparent

    Args:
        w_name (str): Window title
    """
    hwnd = FindWindow(None, w_name)
    SetWindowLong(hwnd, GWL_EXSTYLE, GetWindowLong(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED)
    SetLayeredWindowAttributes(hwnd, RGB(0, 0, 0), 140, LWA_ALPHA)

if __name__ == '__main__':
    transparent_window("MonkeyShot - Screenshot")
