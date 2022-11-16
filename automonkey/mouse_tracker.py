from time import sleep

from tkinter import Tk
from tkinter import Canvas

from pyautogui import size
from pyautogui import position

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
    """PositionTracker
    """
    def __init__(self, follow_mouse: bool = False):
        self.follow_mouse = follow_mouse
        self.window = Tk()  # Was Tk()
        self.window.canvas = None
        self.coords = None
        self.get_coords = False
        self.after = None

    def start(self, get_coords: bool = False):
        """Take the screenshot
        """
        if self.after:
            self.window.after_cancel(self.after)
        if get_coords:
            self.get_coords = True
            self.window.bind('<Control-Button-1>', lambda e: self.destroy_())
        else:
            self.window.bind('<Escape>', lambda e: self.destroy_())
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

        self.after = self.window.after(1, self._crosshair, None)
        self.window.mainloop()
        if get_coords:
            return self.coords
        return None

    def _crosshair(self, coords):
        if self.get_coords:
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
            coords = self._make_coords(coords, x_point, y_point)

        self.window.after(1, self._crosshair, coords)

    def _make_coords(self, coords, x_point: int, y_point: int) -> any:
        if coords is None:
            self.window.canvas.create_text(
                180,
                20,
                text="Press ESC to exit.",
                fill='red',
                font=("Helvetica", 30),
            )
        if self.follow_mouse:
            coords = self._make_coords_1(x_point, y_point)
        else:
            coords = self._make_coords_2(x_point, y_point)
        return coords

    def _make_coords_1(self, x_point: int, y_point: int) -> any:
        return self.window.canvas.create_text(
            self._make_coords_1_x(x_point),
            self._make_coords_1_y(x_point, y_point),
            text=f"x={x_point}, y={y_point}",
            fill='red',
            font=("Helvetica", 20) if x_point < size()[0] + 100 else ("Helvetica", 40),
        )

    def _make_coords_2(self, x_point: int, y_point: int) -> any:
        return self.window.canvas.create_text(
            size()[0] / 2,
            size()[1] / 2,
            text=f"x={x_point}, y={y_point}",
            fill='red',
            font=("Helvetica", 40),
        )

    @staticmethod
    def _make_coords_1_x(x_point: int) -> int:
        return x_point + 100 if x_point < size()[0] - 200 else x_point - 100 if x_point < size()[0] + 100 else size()[0] / 2

    @staticmethod
    def _make_coords_1_y(x_point: int, y_point: int) -> int:
        if x_point > size()[0] + 100:
            return size()[1] / 2
        if (y_point < 70 and x_point < 300):
            return y_point + 100
        if y_point < size()[1] - 200:
            return y_point + 20
        return y_point - 100

    def destroy_(self):
        self.window.after_cancel(self.after)
        self.window.destroy()
