"""Unified snippet model, markdown parser, and snippet manager for QuickType."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        note: Optional[str] = None,
        searchable_text: Optional[str] = None,
        group: Optional[str] = None,
        location: Optional[str] = None,
    ) -> None:
        self.name = name
        self.payload = payload
        self.description = description
        self.note = note
        self.group = group
        self.location = location

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
            "note": self.note,
            "searchable_text": self.searchable_text,
            "group": self.group,
            "location": self.location,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Snippet":
        """Deserialize snippet from dictionary data."""
        payload = data.get("payload", "")
        return Snippet(
            name=data.get("name", ""),
            description=data.get("description"),
            payload=payload,
            note=data.get("note"),
            searchable_text=data.get("searchable_text"),
            group=data.get("group"),
            location=data.get("location"),
        )


def extract_code_block(text: str) -> str:
    """Extract content from exactly one triple-backtick code block."""
    matches = list(re.finditer(r"```\n(.*?)\n```", text, re.DOTALL))

    if len(matches) == 0:
        raise FormatError("No code block (```) found in section")
    if len(matches) > 1:
        raise FormatError(f"Expected exactly 1 code block, found {len(matches)}")

    return matches[0].group(1).strip()


def extract_quote_block(text: str) -> Optional[str]:
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

    # Preserve quote line breaks so tooltip text matches markdown note formatting.
    return "\n".join(blockquote_groups[0]) if blockquote_groups else None


def _section_location(file_path: Path, line_number: int) -> str:
    """Format a file location for VS Code's `-g` flag."""
    return f"{file_path}:{line_number}"


def _heading_sections(lines: List[str], prefix: str) -> List[Tuple[int, str]]:
    """Return (line_index, heading_name) tuples for headings with the given prefix."""
    sections: List[Tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            sections.append((index, line[len(prefix) :].strip()))
    return sections


def _append_parsed_snippet(
    snippets: List[Snippet],
    file_path: Path,
    name: str,
    description: Optional[str],
    section_lines: List[str],
    location_line: int,
    section_label: str,
) -> None:
    """Parse a section body and append a validated snippet."""
    section_text = "\n".join(section_lines)

    try:
        code_block = extract_code_block(section_text)
        quote_block = extract_quote_block(section_text)
        snippets.append(
            Snippet(
                name=name,
                description=description,
                payload=code_block,
                note=quote_block,
                searchable_text=(
                    f"{name} {description} {code_block}" if description else f"{name} {code_block}"
                ),
                group=file_path.stem,
                location=_section_location(file_path, location_line),
            )
        )
    except FormatError as exc:
        raise FormatError(f"Invalid format in {file_path} at section '{section_label}': {exc}") from exc


def parse_markdown_file(file_path: Path) -> List[Snippet]:
    """Parse one markdown file and return snippet entries with strict validation."""
    snippets: List[Snippet] = []
    lines = file_path.read_text(encoding="utf-8").splitlines()

    h1_sections = _heading_sections(lines, "# ")
    for index, (h1_line_index, h1_name) in enumerate(h1_sections):
        h1_end = h1_sections[index + 1][0] if index + 1 < len(h1_sections) else len(lines)
        h1_body_lines = lines[h1_line_index + 1 : h1_end]
        h2_sections = _heading_sections(h1_body_lines, "## ")

        if len(h2_sections) > 1:
            raise FormatError(
                f"Invalid format in {file_path} at section '# {h1_name}': "
                "Expected at most one H2 description"
            )

        description = h2_sections[0][1] if h2_sections else None
        _append_parsed_snippet(
            snippets=snippets,
            file_path=file_path,
            name=h1_name,
            description=description,
            section_lines=h1_body_lines,
            location_line=h1_line_index + 1,
            section_label=f"# {h1_name}",
        )

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
        group: str,
        location: Optional[str] = None,
    ) -> Snippet:
        """Append a snippet section to {group}.md and refresh in-memory pools."""
        source_name = group.strip()
        if not source_name:
            raise ValueError("group must not be empty")

        snippet = Snippet(
            name=name.strip(),
            description=description.strip() if description else None,
            payload=payload,
            group=source_name,
            location=location,
        )
        if not snippet.name:
            raise ValueError("name must not be empty")

        md_path = self.data_dir / f"{source_name}.md"
        block = self._format_markdown_snippet(snippet)
        existing_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        needs_separator = existing_text.strip() != ""

        if existing_text:
            next_line = len(existing_text.splitlines()) + (2 if existing_text.endswith("\n") else 1)
        else:
            next_line = 1

        # H1 is the snippet identity, so location always points to the new H1 line.
        snippet.location = f"{md_path}:{next_line}"

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
