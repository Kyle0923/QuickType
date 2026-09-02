from quicktype.config import Snippet
from quicktype.core import FuzzyMatcher
from quicktype.gui import SnippetSearchWindow
from quicktype.hotkey import HotkeyManager


def test_fuzzy_matcher_handles_fzf_style_subsequence_queries():
    matcher = FuzzyMatcher(threshold=60)
    snippets = [
        Snippet(name="greet", content="Hello there!"),
        Snippet(name="hello", content="Hello world!"),
        Snippet(name="test1", content="First test"),
        Snippet(name="test2", content="Second test"),
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
            Snippet(name="greet", content="Hello there!"),
            Snippet(name="hello", content="Hello world!"),
            Snippet(name="test1", content="First test"),
            Snippet(name="test2", content="Second test"),
        ],
    )

    window.search_var.set("g e t")
    window._on_search_input()

    assert [snippet.name for snippet in window.filtered_snippets] == ["greet"]
    window.destroy()


def test_hotkey_manager_can_update_hotkey_binding():
    manager = HotkeyManager("ctrl+shift+q")

    manager.set_hotkey("alt+space")

    assert manager.hotkey == "alt+space"
