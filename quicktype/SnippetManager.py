"""Unified snippet model, markdown parser, and snippet manager for QuickType."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DEFAULT_DATA_DIR
from .hierarchy import HierarchyManager


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

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.hierarchy_manager = HierarchyManager(self.data_dir)
        self._all_snippets_by_source: Dict[str, List[Snippet]] = {}
        self.snippets: Dict[str, Snippet] = {}
        self._load()

    def _load(self) -> None:
        self._all_snippets_by_source = parse_data_directory(self.data_dir)
        self._recompose_active_pool()

    def _recompose_active_pool(self) -> None:
        """Rebuild active snippets from loaded markdown data and hierarchy state."""
        self.snippets = {}
        for source_name in self.active_source_names():
            for snippet in self._all_snippets_by_source.get(source_name, []):
                self.snippets[snippet.name] = snippet

    def active_source_names(self) -> List[str]:
        """Return active source names based on enabled hierarchy subtrees."""
        return self.hierarchy_manager.get_active_document_names()

    def list_all_snippets(self) -> List[Snippet]:
        """Return every loaded snippet regardless of current subtree filters."""
        all_snippets: List[Snippet] = []
        for snippets in self._all_snippets_by_source.values():
            all_snippets.extend(snippets)
        return all_snippets

    def disable_subtree(self, node_name: str) -> None:
        """Disable a hierarchy subtree and recompose the active snippet pool."""
        self.hierarchy_manager.disable_subtree(node_name)
        self._recompose_active_pool()

    def enable_subtree(self, node_name: str) -> None:
        """Enable a hierarchy subtree and recompose the active snippet pool."""
        self.hierarchy_manager.enable_subtree(node_name)
        self._recompose_active_pool()

    def enable_all_subtrees(self) -> None:
        """Enable all hierarchy subtrees and recompose the active snippet pool."""
        self.hierarchy_manager.enable_all()
        self._recompose_active_pool()

    def set_subtree_enabled(self, node_name: str, enabled: bool) -> None:
        """Set subtree state in one call for checkbox-driven UIs."""
        if enabled:
            self.enable_subtree(node_name)
        else:
            self.disable_subtree(node_name)

    def add_snippet(
        self,
        name: str,
        description: Optional[str],
        payload: str,
        source: str,
    ) -> Snippet:
        """Append a snippet section to {source}.md and refresh in-memory pools."""
        source_name = source.strip()
        if not source_name:
            raise ValueError("source must not be empty")

        snippet = Snippet(
            name=name.strip(),
            description=description.strip() if description else None,
            payload=payload,
            source=source_name,
        )
        if not snippet.name:
            raise ValueError("name must not be empty")

        md_path = self.data_dir / f"{source_name}.md"
        block = self._format_markdown_snippet(snippet)
        needs_separator = md_path.exists() and md_path.read_text(encoding="utf-8").strip() != ""

        with md_path.open("a", encoding="utf-8") as handle:
            if needs_separator:
                handle.write("\n")
            handle.write(block)

        self._all_snippets_by_source.setdefault(source_name, []).append(snippet)
        self._recompose_active_pool()
        return snippet

    @staticmethod
    def _format_markdown_snippet(snippet: Snippet) -> str:
        """Format a snippet using the markdown parser rules."""
        lines = [f"# {snippet.name}"]
        if snippet.description:
            lines.append(f"## {snippet.description}")
        lines.append("```")
        lines.extend(snippet.payload.splitlines() or [""])
        lines.append("```")
        return "\n".join(lines) + "\n"

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
    "parse_data_directory",
    "parse_markdown_file",
]
