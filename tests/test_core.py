from quicktype.SnippetManager import Snippet
from quicktype.core import FuzzyMatcher
from quicktype.gui import SnippetSearchWindow
from quicktype.hotkey import HotkeyManager


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


def test_hotkey_manager_can_update_hotkey_binding():
    manager = HotkeyManager("ctrl+shift+q")

    manager.set_hotkey("alt+space")

    assert manager.hotkey == "alt+space"
