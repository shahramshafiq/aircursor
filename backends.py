"""Mouse backend abstraction.

The engine never touches a real mouse directly. main.py performs the
engine's requested actions on a backend. The real app uses PynputBackend;
tests inject FakeBackend so nothing on screen ever moves.
"""


class MouseBackend:
    """Interface every backend implements."""

    def move(self, x, y):
        raise NotImplementedError

    def click(self, button):
        raise NotImplementedError

    def press(self, button):
        raise NotImplementedError

    def release(self, button):
        raise NotImplementedError

    def scroll(self, dx, dy):
        raise NotImplementedError

    @property
    def screen_size(self):
        raise NotImplementedError


class PynputBackend(MouseBackend):
    def __init__(self):
        from pynput.mouse import Controller, Button
        self._controller = Controller()
        self._button = Button
        self._size = self._detect_screen_size()

    def _detect_screen_size(self):
        try:
            from screeninfo import get_monitors
            monitor = get_monitors()[0]
            if monitor.width and monitor.height:
                return (monitor.width, monitor.height)
        except Exception:
            pass
        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
            return (width, height)
        except Exception:
            pass
        return (1920, 1080)

    def _resolve(self, button):
        if button == "right":
            return self._button.right
        return self._button.left

    def move(self, x, y):
        self._controller.position = (int(x), int(y))

    def click(self, button):
        self._controller.click(self._resolve(button), 1)

    def press(self, button):
        self._controller.press(self._resolve(button))

    def release(self, button):
        self._controller.release(self._resolve(button))

    def scroll(self, dx, dy):
        self._controller.scroll(dx, dy)

    @property
    def screen_size(self):
        return self._size


class FakeBackend(MouseBackend):
    """Records every call. Used by tests. Never touches a real mouse."""

    def __init__(self, screen_size=(1920, 1080)):
        self.calls = []
        self._size = screen_size

    def move(self, x, y):
        self.calls.append(("move", int(x), int(y)))

    def click(self, button):
        self.calls.append(("click", button))

    def press(self, button):
        self.calls.append(("press", button))

    def release(self, button):
        self.calls.append(("release", button))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))

    @property
    def screen_size(self):
        return self._size
