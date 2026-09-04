from quicktype.SnippetManager import Snippet
from quicktype.core import FuzzyMatcher
from quicktype.gui import SnippetSearchWindow
from quicktype.hotkey import HotkeyManager
import sys


def test_fuzzy_matcher_handles_fzf_style_subsequence_queries():
    matcher = FuzzyMatcher(threshold=60)
    snippets = [
        Snippet(name="greet", payload="Hello there!"),
        Snippet(name="hello", payload="Hello world!"),
        Snippet(name="test1", payload="First test"),
        Snippet(name="test2", payload="Second test"),
    ]

    results = matcher.search("g t r", snippets)
    assert [snippet.name for snippet in results] == ["greet"]

    and_results = matcher.search("g e t", snippets)
    assert [snippet.name for snippet in and_results] == ["greet"]


def test_search_window_uses_fuzzy_matching_for_space_separated_queries():
    window = SnippetSearchWindow(
        on_select=lambda snippet_name: None,
        on_close=lambda: None,
        snippets=[
            Snippet(name="greet", payload="Hello there!"),
            Snippet(name="hello", payload="Hello world!"),
            Snippet(name="test1", payload="First test"),
            Snippet(name="test2", payload="Second test"),
        ],
    )

    window.search_var.set("g e t")
    window._on_search_input()

    assert [snippet.name for snippet in window.filtered_snippets] == ["greet"]
    window.destroy()


def test_search_window_navigation_moves_selection_with_arrow_keys():
    window = SnippetSearchWindow(
        on_select=lambda snippet_name: None,
        on_close=lambda: None,
        snippets=[
            Snippet(name="alpha", payload="A"),
            Snippet(name="beta", payload="B"),
            Snippet(name="gamma", payload="C"),
        ],
    )

    window.filtered_snippets = window.snippets
    window._update_snippet_list(window.filtered_snippets)

    window._move_selection(1)
    assert window.selected_index == 1
    assert window.filtered_snippets[window.selected_index].name == "beta"

    window._move_selection(-1)
    assert window.selected_index == 0
    assert window.filtered_snippets[window.selected_index].name == "alpha"

    window.destroy()


def test_search_window_ctrl_w_removes_only_last_word():
    window = object.__new__(SnippetSearchWindow)
    window.search_var = type("SearchVar", (), {"get": lambda self: "aa bb cc", "set": lambda self, value: setattr(self, "value", value)})()
    window.search_var.value = "aa bb cc"
    window.search_var.get = lambda: window.search_var.value
    window.search_var.set = lambda value: setattr(window.search_var, "value", value)

    class FakeEntry:
        def __init__(self):
            self.cursor = len("aa bb cc")

        def index(self, marker):
            return self.cursor

        def icursor(self, pos):
            self.cursor = pos

    window.search_entry = FakeEntry()

    window._on_ctrl_w(None)

    assert window.search_var.get() == "aa bb"
    assert window.search_entry.cursor == len("aa bb")


def test_search_window_ctrl_d_clears_search_box():
    window = object.__new__(SnippetSearchWindow)
    window.search_var = type("SearchVar", (), {"get": lambda self: "hello", "set": lambda self, value: setattr(self, "value", value)})()
    window.search_var.value = "hello"
    window.search_var.get = lambda: window.search_var.value
    window.search_var.set = lambda value: setattr(window.search_var, "value", value)

    class FakeEntry:
        def __init__(self):
            self.cursor = len("hello")

        def icursor(self, pos):
            self.cursor = pos

    window.search_entry = FakeEntry()

    result = window._on_ctrl_d(None)

    assert result == "break"
    assert window.search_var.get() == ""
    assert window.search_entry.cursor == 0


def test_search_window_escape_hides_window():
    window = object.__new__(SnippetSearchWindow)
    called = {"hidden": False}

    def fake_hide() -> None:
        called["hidden"] = True

    window._hide_window = fake_hide

    result = window._on_escape(None)

    assert result == "break"
    assert called["hidden"] is True


def test_search_window_get_final_text_trims_tk_trailing_newline():
    window = object.__new__(SnippetSearchWindow)

    class FakeFinalText:
        def get(self, start, end):
            _ = (start, end)
            return "line1\nline2\n"

    window.final_text = FakeFinalText()

    assert window._get_final_text() == "line1\nline2"


def test_search_window_insert_hides_before_deferred_insert_callback():
    window = object.__new__(SnippetSearchWindow)
    window.selected_index = 0
    window.filtered_snippets = [Snippet(name="demo", payload="x")]

    order = []

    class FakeRoot:
        def after(self, delay_ms, callback):
            order.append(f"after:{delay_ms}")
            callback()

    window.root = FakeRoot()
    window._get_final_text = lambda: "final value"

    def fake_hide() -> None:
        order.append("hide")

    def fake_on_select(text: str, mode: str) -> None:
        order.append(f"select:{text}:{mode}")

    window._hide_window = fake_hide
    window.on_select = fake_on_select

    window._insert_selected()

    assert order == ["hide", "after:80", "select:final value:paste"]


def test_search_window_enter_handler_triggers_insert_and_breaks_event():
    window = object.__new__(SnippetSearchWindow)
    called = {"mode": ""}

    def fake_insert(mode="paste") -> None:
        called["mode"] = mode

    window._insert_selected = fake_insert

    result = window._on_enter(None)

    assert result == "break"
    assert called["mode"] == "paste"


def test_search_window_alt_enter_handler_uses_type_mode():
    window = object.__new__(SnippetSearchWindow)
    called = {"mode": ""}

    def fake_insert(mode="paste") -> None:
        called["mode"] = mode

    window._insert_selected = fake_insert

    result = window._on_alt_enter(None)

    assert result == "break"
    assert called["mode"] == "type"


def test_snippet_engine_insert_text_uses_insert_callback():
    from quicktype.core import SnippetEngine

    captured = {"text": ""}

    def fake_insert(value: str) -> None:
        captured["text"] = value

    engine = SnippetEngine(manager=object())
    engine.set_insert_callback(fake_insert)
    engine.insert_text("edited payload")

    assert captured["text"] == "edited payload"


def test_text_inserter_uses_keyboard_delay_argument(monkeypatch):
    from quicktype.core import TextInserter

    captured = {"text": None, "kwargs": None}

    class FakeKeyboard:
        @staticmethod
        def write(text, **kwargs):
            captured["text"] = text
            captured["kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "keyboard", FakeKeyboard)

    TextInserter.insert("hello")

    assert captured["text"] == "hello"
    assert captured["kwargs"] == {"delay": 0.05}


def test_text_inserter_paste_uses_ctrl_v(monkeypatch):
    from quicktype.core import TextInserter

    pressed = {"keys": None}

    class FakeKeyboard:
        @staticmethod
        def press_and_release(keys):
            pressed["keys"] = keys

    class FakeTk:
        def withdraw(self):
            return None

        def clipboard_clear(self):
            return None

        def clipboard_append(self, value):
            self.value = value

        def update(self):
            return None

        def destroy(self):
            return None

    monkeypatch.setitem(sys.modules, "keyboard", FakeKeyboard)
    monkeypatch.setattr("tkinter.Tk", lambda: FakeTk())

    TextInserter.paste("hello")

    assert pressed["keys"] == "ctrl+v"


def test_hotkey_manager_can_update_hotkey_binding():
    manager = HotkeyManager("ctrl+shift+q")

    manager.set_hotkey("alt+space")

    assert manager.hotkey == "alt+space"
