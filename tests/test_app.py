from quicktype.app import QuickTypeApp


class _FakeGui:
    def __init__(self, visible: bool, foreground: bool):
        self._visible = visible
        self._foreground = foreground
        self.hidden = False
        self.shown = False
        self.brought_to_front = False
        self.updated_with = None
        self.scheduled = []

        class _FakeRoot:
            def __init__(self, outer):
                self.outer = outer

            def after(self, delay_ms, callback):
                self.outer.scheduled.append(delay_ms)
                callback()

        self.root = _FakeRoot(self)

    def is_visible(self):
        return self._visible

    def is_foreground(self):
        return self._foreground

    def hide(self):
        self.hidden = True

    def show(self):
        self.shown = True

    def bring_to_front(self):
        self.brought_to_front = True

    def update_snippets(self, snippets):
        self.updated_with = snippets


class _FakeEngine:
    def list_snippets(self):
        return ["a", "b"]


def test_hotkey_hides_when_window_is_visible_and_focused():
    app = object.__new__(QuickTypeApp)
    app.gui_window = _FakeGui(visible=True, foreground=True)
    app.engine = _FakeEngine()

    app._on_hotkey_pressed()

    assert app.gui_window.scheduled == [0]
    assert app.gui_window.hidden is True
    assert app.gui_window.shown is False


def test_hotkey_refocuses_when_window_visible_but_not_focused():
    app = object.__new__(QuickTypeApp)
    app.gui_window = _FakeGui(visible=True, foreground=False)
    app.engine = _FakeEngine()

    app._on_hotkey_pressed()

    assert app.gui_window.scheduled == [0]
    assert app.gui_window.hidden is False
    assert app.gui_window.shown is False
    assert app.gui_window.brought_to_front is True
    assert app.gui_window.updated_with is None
