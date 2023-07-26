from pyautogui import move  # It is used

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
