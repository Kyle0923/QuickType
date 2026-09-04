"""Hierarchy parsing and tree composition for .data/root.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple


class HierarchyFormatError(ValueError):
    """Raised when root.yaml has invalid structure or references."""


@dataclass
class TreeNode:
    """A node in the markdown document hierarchy tree."""

    name: str
    children: List["TreeNode"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


@dataclass
class DocumentTree:
    """Composed hierarchy tree loaded from root.yaml."""

    root: TreeNode

    def all_nodes(self) -> List[TreeNode]:
        """Return nodes in pre-order traversal."""
        ordered: List[TreeNode] = []

        def visit(node: TreeNode) -> None:
            ordered.append(node)
            for child in node.children:
                visit(child)

        visit(self.root)
        return ordered

    def leaf_names(self) -> List[str]:
        """Return leaf node names in traversal order."""
        leaves: List[str] = []
        for node in self.all_nodes():
            if node.name != self.root.name and node.is_leaf:
                leaves.append(node.name)
        return leaves

    def node_names(self) -> List[str]:
        """Return all node names except the synthetic root."""
        return [node.name for node in self.all_nodes() if node.name != self.root.name]


class HierarchyManager:
    """Parse root.yaml and manage runtime subtree filtering state."""

    ROOT_FILE = "root.yaml"

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.tree = self.compose(self.data_dir)
        self._node_index: Dict[str, TreeNode] = {}
        self._parent_index: Dict[str, Optional[str]] = {}
        self._disabled_subtrees: Set[str] = set()
        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build fast lookup indexes for node and parent relationships."""

        def visit(node: TreeNode, parent: Optional[str]) -> None:
            if node.name in self._node_index:
                raise HierarchyFormatError(f"Duplicate hierarchy node name: {node.name}")
            self._node_index[node.name] = node
            self._parent_index[node.name] = parent
            for child in node.children:
                visit(child, node.name)

        visit(self.tree.root, None)

    def has_node(self, node_name: str) -> bool:
        """Return True when a node exists in the tree."""
        return node_name in self._node_index

    def disable_subtree(self, node_name: str) -> None:
        """Disable a subtree so its markdown files are excluded from the active pool."""
        self._assert_node_exists(node_name)
        self._disabled_subtrees.add(node_name)

    def enable_subtree(self, node_name: str) -> None:
        """Enable a subtree previously disabled with disable_subtree."""
        self._assert_node_exists(node_name)
        self._disabled_subtrees.discard(node_name)

    def enable_all(self) -> None:
        """Enable all subtrees in the hierarchy."""
        self._disabled_subtrees.clear()

    def disabled_subtrees(self) -> List[str]:
        """Return disabled subtrees in sorted order."""
        return sorted(self._disabled_subtrees)

    def is_node_active(self, node_name: str) -> bool:
        """Return True when node and all its ancestors are enabled."""
        self._assert_node_exists(node_name)
        current: Optional[str] = node_name
        while current is not None:
            if current in self._disabled_subtrees:
                return False
            current = self._parent_index[current]
        return True

    def get_active_node_names(self) -> List[str]:
        """Return enabled node names in traversal order (excluding synthetic root)."""
        names: List[str] = []
        for name in self.tree.node_names():
            if self.is_node_active(name):
                names.append(name)
        return names

    def get_mapped_document_names(self) -> List[str]:
        """Return mapped document names in hierarchy order.

        Leaf nodes are guaranteed by compose validation.
        Map nodes are optional and included only when their markdown file exists.
        """
        names: List[str] = []
        for node_name in self.tree.node_names():
            if self._document_path(node_name).exists():
                names.append(node_name)
        return names

    def get_subtree_node_names(self, node_name: str) -> List[str]:
        """Return all node names inside a subtree, including the root node itself."""
        self._assert_node_exists(node_name)
        node = self._node_index[node_name]
        return [child.name for child in self._iter_subtree(node)]

    def get_active_document_names(self) -> List[str]:
        """Return active mapped document names in hierarchy order.

        Leaf nodes are always expected to have files by compose validation.
        Map nodes are optional and included only when their markdown file exists.
        """
        names: List[str] = []
        for node_name in self.tree.node_names():
            if not self.is_node_active(node_name):
                continue
            if self._document_path(node_name).exists():
                names.append(node_name)
        return names

    def _assert_node_exists(self, node_name: str) -> None:
        if node_name not in self._node_index:
            raise HierarchyFormatError(f"Hierarchy node not found: {node_name}")

    def _document_path(self, document_name: str) -> Path:
        """Map a document name to its markdown file path for file I/O."""
        return self.data_dir / f"{document_name}.md"

    def _iter_subtree(self, node: TreeNode) -> Iterator[TreeNode]:
        yield node
        for child in node.children:
            yield from self._iter_subtree(child)

    @classmethod
    def compose(cls, data_dir: Path) -> DocumentTree:
        """Parse and validate root.yaml from a data directory."""
        root_file = data_dir / cls.ROOT_FILE
        if not root_file.exists():
            raise HierarchyFormatError(f"Missing hierarchy file: {root_file}")

        tree = cls._parse_root_yaml(root_file)
        cls._validate_leaf_files(data_dir, tree)
        return tree

    @classmethod
    def get_mapped_document_names_from_tree(cls, data_dir: Path, tree: DocumentTree) -> List[str]:
        """Return mapped document names in tree order.

        Leaf nodes must exist (validated by compose).
        Map nodes are optional and included only when a matching markdown file exists.
        """
        names: List[str] = []
        for name in tree.node_names():
            md_path = data_dir / f"{name}.md"
            if md_path.exists():
                names.append(name)
        return names

    @classmethod
    def _validate_leaf_files(cls, data_dir: Path, tree: DocumentTree) -> None:
        missing = [name for name in tree.leaf_names() if not (data_dir / f"{name}.md").exists()]
        if missing:
            names = ", ".join(missing)
            raise HierarchyFormatError(f"Leaf node markdown file(s) missing: {names}")

    @classmethod
    def _parse_root_yaml(cls, root_file: Path) -> DocumentTree:
        lines = root_file.read_text(encoding="utf-8").splitlines()
        entries = cls._clean_lines(lines)
        if not entries:
            raise HierarchyFormatError("root.yaml is empty")

        first_line_no, first_indent, first_text = entries[0]
        if first_indent != 0 or first_text != "root:":
            raise HierarchyFormatError(
                f"root.yaml must start with 'root:' at column 1 (line {first_line_no})"
            )

        nodes, next_index = cls._parse_list(entries, 1, required_indent=None)
        if next_index != len(entries):
            line_no, _, text = entries[next_index]
            raise HierarchyFormatError(f"Unexpected content at line {line_no}: {text}")

        return DocumentTree(root=TreeNode(name="root", children=nodes))

    @staticmethod
    def _clean_lines(lines: List[str]) -> List[Tuple[int, int, str]]:
        cleaned: List[Tuple[int, int, str]] = []
        for index, raw_line in enumerate(lines, 1):
            if "\t" in raw_line:
                raise HierarchyFormatError(f"Tabs are not allowed in root.yaml (line {index})")

            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            cleaned.append((index, indent, stripped))

        return cleaned

    @classmethod
    def _parse_list(
        cls,
        entries: List[Tuple[int, int, str]],
        start_index: int,
        required_indent: Optional[int],
    ) -> Tuple[List[TreeNode], int]:
        if start_index >= len(entries):
            raise HierarchyFormatError("Expected a list under root:, but file ended")

        first_line_no, first_indent, first_text = entries[start_index]
        if required_indent is None:
            required_indent = first_indent

        if not first_text.startswith("- "):
            raise HierarchyFormatError(
                f"Expected list item beginning with '- ' at line {first_line_no}"
            )

        nodes: List[TreeNode] = []
        idx = start_index

        while idx < len(entries):
            line_no, indent, text = entries[idx]

            if indent < required_indent:
                break
            if indent > required_indent:
                raise HierarchyFormatError(
                    f"Unexpected indentation at line {line_no}; expected {required_indent} spaces"
                )
            if not text.startswith("- "):
                raise HierarchyFormatError(
                    f"Expected list item beginning with '- ' at line {line_no}"
                )

            body = text[2:].strip()
            if not body:
                raise HierarchyFormatError(f"Empty list item at line {line_no}")

            if body.endswith(":"):
                name = body[:-1].strip()
                if not name:
                    raise HierarchyFormatError(f"Empty map key at line {line_no}")

                children, idx = cls._parse_list(entries, idx + 1, required_indent + 2)
                nodes.append(TreeNode(name=name, children=children))
                continue

            nodes.append(TreeNode(name=body))
            idx += 1

        return nodes, idx


__all__ = [
    "DocumentTree",
    "HierarchyFormatError",
    "HierarchyManager",
    "TreeNode",
]
