"""Configuration and snippet management for QuickType."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import ensure_config_dir


class Snippet:
    """Represents a single snippet with name, content, and optional metadata."""

    def __init__(
        self,
        name: str,
        content: str,
        tags: Optional[List[str]] = None,
        shortcut: Optional[str] = None,
    ):
        """
        Initialize a Snippet.

        Args:
            name: Unique identifier for the snippet.
            content: Text to insert when snippet is invoked.
            tags: Optional list of tags for categorization.
            shortcut: Optional keyboard shortcut (future use).
        """
        self.name = name
        self.content = content
        self.tags = tags or []
        self.shortcut = shortcut

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize snippet to dictionary.

        Returns:
            Dictionary representation of the snippet.
        """
        return {
            "name": self.name,
            "content": self.content,
            "tags": self.tags,
            "shortcut": self.shortcut,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Snippet":
        """
        Deserialize snippet from dictionary.

        Args:
            data: Dictionary with snippet data.

        Returns:
            Snippet instance.
        """
        return Snippet(
            name=data["name"],
            content=data["content"],
            tags=data.get("tags", []),
            shortcut=data.get("shortcut"),
        )


class SnippetManager:
    """Manages loading, saving, and accessing snippets from configuration storage."""

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize SnippetManager.

        Args:
            storage_path: Path to snippets JSON file. If None, uses default location.
        """
        if storage_path is None:
            config_dir = ensure_config_dir()
            storage_path = config_dir / "snippets.json"

        self.storage_path = storage_path
        self.snippets: Dict[str, Snippet] = {}
        self._load()

    def _load(self) -> None:
        """Load snippets from storage file if it exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.snippets = {
                        name: Snippet.from_dict(snippet_data)
                        for name, snippet_data in data.items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                raise ValueError(f"Invalid snippets file: {e}")

    def save(self) -> None:
        """Save snippets to storage file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            data = {name: snippet.to_dict() for name, snippet in self.snippets.items()}
            json.dump(data, f, indent=2)

    def add_snippet(self, snippet: Snippet) -> None:
        """
        Add a snippet to the manager.

        Args:
            snippet: Snippet to add.
        """
        self.snippets[snippet.name] = snippet
        self.save()

    def remove_snippet(self, name: str) -> None:
        """
        Remove a snippet by name.

        Args:
            name: Name of snippet to remove.

        Raises:
            KeyError: If snippet doesn't exist.
        """
        del self.snippets[name]
        self.save()

    def get_snippet(self, name: str) -> Optional[Snippet]:
        """
        Get a snippet by name.

        Args:
            name: Name of snippet to retrieve.

        Returns:
            Snippet if found, None otherwise.
        """
        return self.snippets.get(name)

    def list_snippets(self) -> List[Snippet]:
        """
        Get all snippets.

        Returns:
            List of all stored snippets.
        """
        return list(self.snippets.values())

    def search_by_tag(self, tag: str) -> List[Snippet]:
        """
        Find snippets with a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of matching snippets.
        """
        return [s for s in self.snippets.values() if tag in s.tags]
