"""Core snippet engine and keyboard hook management for QuickType."""

from typing import Callable, List, Optional

from iterfzf import iterfzf

from .SnippetManager import Snippet, SnippetManager


class FuzzyMatcher:
    """Handles fuzzy matching of snippet names using the fzf algorithm."""

    def __init__(self, threshold: int = 60):
        """
        Initialize FuzzyMatcher.

        Args:
            threshold: Kept for API compatibility; matching is delegated to iterfzf.
        """
        self.threshold = threshold

    def search(self, query: str, snippets: List[Snippet]) -> List[Snippet]:
        """
        Search snippets using the fzf-style matching algorithm from iterfzf.

        Args:
            query: User input query string.
            snippets: List of snippets to search.

        Returns:
            Sorted list of matching snippets (best matches first).
        """
        if not query:
            return snippets

        names = [snippet.name for snippet in snippets]
        matched_names = iterfzf(
            names,
            multi=True,
            case_sensitive=False,
            extended=True,
            sort=True,
            __extra__=[f"--filter={query}"]
        )

        if not matched_names:
            return []
        if isinstance(matched_names, str):
            matched_names = [matched_names]

        name_to_snippet = {snippet.name: snippet for snippet in snippets}
        return [
            name_to_snippet[name]
            for name in matched_names
            if name in name_to_snippet
        ]


class SnippetEngine:
    """Main snippet engine managing snippets and keyboard integration."""

    def __init__(self, manager: Optional[SnippetManager] = None):
        """
        Initialize SnippetEngine.

        Args:
            manager: SnippetManager instance. If None, creates a new one.
        """
        self.manager = manager or SnippetManager()
        self.fuzzy_matcher = FuzzyMatcher(threshold=60)
        self.insert_callback: Optional[Callable[[str], None]] = None

    def set_insert_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set the callback function for inserting text.

        This allows decoupling snippet logic from platform-specific insertion.

        Args:
            callback: Function that accepts text string and performs insertion.
        """
        self.insert_callback = callback

    def search_snippets(self, query: str) -> List[Snippet]:
        """
        Search for snippets matching the query.

        Args:
            query: User search query.

        Returns:
            List of matching snippets sorted by relevance.
        """
        snippets = self.manager.list_snippets()
        return self.fuzzy_matcher.search(query, snippets)

    def insert_snippet(self, snippet_name: str) -> bool:
        """
        Insert a snippet's content via the registered callback.

        Args:
            snippet_name: Name of snippet to insert.

        Returns:
            True if successful, False if snippet not found or no callback set.
        """
        if not self.insert_callback:
            raise RuntimeError("Insert callback not set. Use set_insert_callback().")

        snippet = self.manager.get_snippet(snippet_name)
        if not snippet:
            return False

        self.insert_callback(snippet.payload)
        return True

    def add_snippet(self, name: str, content: str) -> None:
        """
        Add a new snippet.

        Args:
            name: Unique snippet name.
            content: Text content to insert.
        """
        snippet = Snippet(name=name, payload=content)
        self.manager.add_snippet(snippet)

    def remove_snippet(self, name: str) -> bool:
        """
        Remove a snippet.

        Args:
            name: Name of snippet to remove.

        Returns:
            True if successful, False if snippet not found.
        """
        try:
            self.manager.remove_snippet(name)
            return True
        except KeyError:
            return False

    def list_snippets(self) -> List[Snippet]:
        """
        Get all available snippets.

        Returns:
            List of all snippets.
        """
        return self.manager.list_snippets()


class TextInserter:
    """Handles platform-specific text insertion into the active window."""

    @staticmethod
    def insert(text: str) -> None:
        """
        Insert text into the currently active window.

        Uses platform-specific methods:
        - Windows: keyboard.write() or clipboard + paste
        - macOS: PyObjC + keyboard
        - Linux: xdotool or keyboard library

        Args:
            text: Text to insert.
        """
        # Use keyboard library for cross-platform text insertion
        import keyboard as kb

        kb.write(text, interval=0.05)
