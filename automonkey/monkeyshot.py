"""cyberMonkey provides GUI tools for autoMonkey
"""
from os import system
from os.path import join
from os.path import abspath
from os.path import dirname
from os.path import expanduser

from pathlib import Path

from threading import Thread

from OpenGL.GL import glClearColor
from OpenGL.GL import glClear
from OpenGL.GL import glColor3f
from OpenGL.GL import glPointSize
from OpenGL.GL import glVertex2f
from OpenGL.GL import glBegin
from OpenGL.GL import glEnd
from OpenGL.GL import glFlush
from OpenGL.GL import GL_COLOR_BUFFER_BIT
from OpenGL.GL import GL_LINES

from OpenGL.GLU import gluOrtho2D

from OpenGL.GLUT import glutInit
from OpenGL.GLUT import glutIdleFunc
from OpenGL.GLUT import glutFullScreen
from OpenGL.GLUT import glutCreateWindow
from OpenGL.GLUT import glutSwapBuffers
from OpenGL.GLUT import glutInitDisplayMode
from OpenGL.GLUT import glutInitWindowSize
from OpenGL.GLUT import glutPostRedisplay
from OpenGL.GLUT import glutDisplayFunc
from OpenGL.GLUT import glutMouseFunc
from OpenGL.GLUT import glutMainLoop
from OpenGL.GLUT import glutLeaveMainLoop
from OpenGL.GLUT import GLUT_LEFT_BUTTON
from OpenGL.GLUT import GLUT_DOWN
from OpenGL.GLUT import GLUT_DOUBLE
from OpenGL.GLUT import GLUT_RGBA

from win32gui import FindWindow
from win32gui import DestroyWindow
from win32gui import SetForegroundWindow

from pyautogui import keyUp
from pyautogui import keyDown
from pyautogui import position
from pyautogui import screenshot


class MonkeyShot:
    """Take screenshot of specific region, using a croshair for selection
    """
    def __init__(self):
        self._window_name = "MonkeyShot - Screenshot"
        self._handle = ""
        self._clicks = 0
        self._points = []
        self.location = expanduser("~/Desktop")
        self.name = "MonkeyShotScreenShort.jpg"

    def set_location(self, loc: str):
        """Set location where to save the screenshot

        Args:
            loc (str): Folder Path
        """
        self.location = loc

    def set_name(self, nam: str):
        """[summary]

        Args:
            nam (str): Filename for the screenshot
        """
        self.name = nam

    def shoot(self):
        """Take the screenshot
        """
        gui_thread = Thread(target=self._show_gui)
        transparency_thread = Thread(target=self._make_transparent)

        gui_thread.start()
        transparency_thread.start()

        gui_thread.join()
        transparency_thread.join()

    def _take_screenshot(self, points_list):
        first_point = points_list[0]
        second_point = points_list[1]
        screenshot(Path(join(self.location, self.name)),
                   region=(first_point[0],
                           first_point[1],
                           second_point[0] - first_point[0],
                           second_point[1] - first_point[1]))
        glutLeaveMainLoop()

    def _on_click(self, button, state, x_value, y_value):
        if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
            self._clicks += 1
            self._points.append((x_value, y_value))
            if self._clicks == 2:
                #hwnd = FindWindow(None, self._window_name)
                DestroyWindow(self._handle)
                self._take_screenshot(self._points)

    @staticmethod
    def _clear_screen():
        glClearColor(0.0, 0.0, 0.0, 1.0)
        gluOrtho2D(-1.0, 1.0, -1.0, 1.0)

    def _crosshair(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glColor3f(1.0, 0.0, 0.0)
        glPointSize(5.0)
        glBegin(GL_LINES)

        cur_pos = position()
        x_point = 1 / 960 * cur_pos[0] - 1
        y_point = (1 / 540 * cur_pos[1] - 1) * (-1)

        # Horizontal line
        glVertex2f(-1.0, y_point)
        glVertex2f(1.0, y_point)

        # Vertical Line
        glVertex2f(x_point, -1.0)
        glVertex2f(x_point, 1.0)

        glEnd()
        glutSwapBuffers()
        glutPostRedisplay()
        glFlush()

    def _show_gui(self):
        glutInit()
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)
        glutInitWindowSize(600, 600)
        glutCreateWindow(self._window_name)
        self._handle = FindWindow(None, self._window_name)
        keyDown('alt')
        SetForegroundWindow(self._handle)
        keyUp('alt')
        glutFullScreen()
        glutIdleFunc(self._crosshair)
        glutMouseFunc(self._on_click)

        glutDisplayFunc(self._crosshair)
        self._clear_screen()

        glutMainLoop()

    @staticmethod
    def _make_transparent():
        _script_path = abspath(dirname(__file__))
        _transparency = "transparency.py"
        system(f'python "{join(_script_path, _transparency)}"')
