"""Unified snippet model, markdown parser, and snippet manager for QuickType."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_default_snippets_path() -> Path:
    """Return the default repo-relative snippets directory."""
    return Path(__file__).resolve().parent.parent / ".data"


def get_data_dir() -> Path:
    """Backward-compatible alias for the default snippets directory."""
    return get_default_snippets_path()


class FormatError(Exception):
    """Raised when markdown snippet format is invalid."""


class Snippet:
    """Unified snippet model used by parser, manager, and UI code."""

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        payload: str = "",
        searchable_text: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        self.name = name
        self.payload = payload
        self.description = description
        self.source = source

        if searchable_text is None:
            parts = [self.name]
            if self.description:
                parts.append(self.description)
            if self.payload:
                parts.append(self.payload)
            self.searchable_text = " ".join(parts)
        else:
            self.searchable_text = searchable_text

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snippet to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "payload": self.payload,
            "searchable_text": self.searchable_text,
            "source": self.source,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Snippet":
        """Deserialize snippet from dictionary data."""
        payload = data.get("payload", "")
        return Snippet(
            name=data.get("name", ""),
            description=data.get("description"),
            payload=payload,
            searchable_text=data.get("searchable_text"),
            source=data.get("source"),
        )


def extract_code_block(text: str) -> str:
    """Extract content from exactly one triple-backtick code block."""
    matches = list(re.finditer(r"```\n(.*?)\n```", text, re.DOTALL))

    if len(matches) == 0:
        raise FormatError("No code block (```) found in section")
    if len(matches) > 1:
        raise FormatError(f"Expected exactly 1 code block, found {len(matches)}")

    return matches[0].group(1).strip()


def extract_quote_block(text: str) -> str:
    """Extract a single contiguous blockquote block (if present)."""
    lines = text.split("\n")
    blockquote_groups: List[List[str]] = []
    current_group: List[str] = []

    for line in lines:
        if line.startswith(">"):
            current_group.append(line[1:].strip())
        elif current_group:
            blockquote_groups.append(current_group)
            current_group = []

    if current_group:
        blockquote_groups.append(current_group)

    if len(blockquote_groups) > 1:
        raise FormatError(f"Expected at most 1 blockquote block, found {len(blockquote_groups)}")

    return " ".join(blockquote_groups[0]) if blockquote_groups else ""


def parse_markdown_file(file_path: Path) -> List[Snippet]:
    """Parse one markdown file and return snippet entries with strict validation."""
    snippets: List[Snippet] = []
    content = file_path.read_text(encoding="utf-8")

    h1_pattern = r"^# (.+)$"
    h1_blocks = re.split(h1_pattern, content, flags=re.MULTILINE)

    for i in range(1, len(h1_blocks), 2):
        h1_name = h1_blocks[i].strip()
        h1_content_block = h1_blocks[i + 1] if i + 1 < len(h1_blocks) else ""

        h2_pattern = r"^## (.+)$"
        h2_blocks = re.split(h2_pattern, h1_content_block, flags=re.MULTILINE)

        if len(h2_blocks) <= 1:
            try:
                code_block = extract_code_block(h1_content_block)
                _ = extract_quote_block(h1_content_block)
                snippets.append(
                    Snippet(
                        name=h1_name,
                        description=None,
                        payload=code_block,
                        searchable_text=f"{h1_name} {code_block}",
                        source=file_path.stem,
                    )
                )
            except FormatError as exc:
                raise FormatError(
                    f"Invalid format in {file_path} at section '# {h1_name}': {exc}"
                ) from exc
        else:
            for j in range(1, len(h2_blocks), 2):
                h2_name = h2_blocks[j].strip()
                h2_content_block = h2_blocks[j + 1] if j + 1 < len(h2_blocks) else ""

                try:
                    code_block = extract_code_block(h2_content_block)
                    _ = extract_quote_block(h2_content_block)
                    snippets.append(
                        Snippet(
                            name=h1_name,
                            description=h2_name,
                            payload=code_block,
                            searchable_text=f"{h1_name} {h2_name} {code_block}",
                            source=file_path.stem,
                        )
                    )
                except FormatError as exc:
                    raise FormatError(
                        f"Invalid format in {file_path} at section '# {h1_name} / ## {h2_name}': {exc}"
                    ) from exc

    return snippets


def parse_data_directory(data_dir: Path) -> Dict[str, List[Snippet]]:
    """Parse all markdown files from a data directory."""
    snippets_by_file: Dict[str, List[Snippet]] = {}

    for md_file in sorted(data_dir.glob("*.md")):
        snippets_by_file[md_file.stem] = parse_markdown_file(md_file)

    return snippets_by_file


class SnippetManager:
    """Manage loading, saving, and querying snippets."""

    DEFAULT_DATA_DIR = get_default_snippets_path()

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir is not None else self.DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snippets: Dict[str, Snippet] = {}
        self._load()

    def _load(self) -> None:
        snippets_by_file = parse_data_directory(self.data_dir)

        for snippets in snippets_by_file.values():
            for snippet in snippets:
                self.snippets[snippet.name] = snippet

        if self.snippets:
            return

        storage_path = self.data_dir / "snippets.json"
        if not storage_path.exists():
            return

        try:
            with storage_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid snippets file: {exc}") from exc

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for entry in value:
                        snippet = Snippet.from_dict(entry)
                        if snippet.name:
                            if not snippet.source:
                                snippet.source = key
                            self.snippets[snippet.name] = snippet
                elif isinstance(value, dict):
                    snippet = Snippet.from_dict(value)
                    if snippet.name:
                        self.snippets[snippet.name] = snippet

    def save(self) -> None:
        """Write a JSON backup for compatibility with existing CLI flow."""
        storage_path = self.data_dir / "snippets.json"
        payload: Dict[str, List[Dict[str, Any]]] = {}

        for snippet in self.snippets.values():
            file_key = Path(snippet.source).stem if snippet.source else "snippets"
            payload.setdefault(file_key, []).append(snippet.to_dict())

        with storage_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def add_snippet(self, snippet: Snippet) -> None:
        self.snippets[snippet.name] = snippet
        self.save()

    def remove_snippet(self, name: str) -> bool:
        if name not in self.snippets:
            return False
        del self.snippets[name]
        self.save()
        return True

    def get_snippet(self, name: str) -> Optional[Snippet]:
        return self.snippets.get(name)

    def list_snippets(self) -> List[Snippet]:
        return list(self.snippets.values())

    def search_by_tag(self, tag: str) -> List[Snippet]:
        return []


__all__ = [
    "FormatError",
    "Snippet",
    "SnippetManager",
    "extract_code_block",
    "extract_quote_block",
    "get_data_dir",
    "get_default_snippets_path",
    "parse_data_directory",
    "parse_markdown_file",
]
