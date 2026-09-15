from pathlib import Path

import pytest

from quicktype.hierarchy import HierarchyFormatError, HierarchyManager


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_hierarchy_manager_composes_nested_tree_and_leafs(tmp_path: Path) -> None:
    data_dir = tmp_path

    _write(
        data_dir / "root.yaml",
        """root:
  - windbg:
    - pagefault
    - crashdump
""",
    )
    _write(data_dir / "pagefault.md", "# pf\n```\n!gpagefault\n```\n")
    _write(data_dir / "crashdump.md", "# cd\n```\n.dump /ma\n```\n")

    tree = HierarchyManager.compose(data_dir)

    assert tree.node_names() == ["windbg", "pagefault", "crashdump"]
    assert tree.leaf_names() == ["pagefault", "crashdump"]


def test_hierarchy_manager_rejects_missing_leaf_markdown(tmp_path: Path) -> None:
    data_dir = tmp_path

    _write(
        data_dir / "root.yaml",
        """root:
  - shell:
    - pwsh
""",
    )

    with pytest.raises(HierarchyFormatError, match=r"Leaf node markdown file\(s\) missing: pwsh"):
        HierarchyManager.compose(data_dir)


def test_hierarchy_manager_rejects_branch_markdown_files(tmp_path: Path) -> None:
    data_dir = tmp_path

    _write(
        data_dir / "root.yaml",
        """root:
  - shell:
    - pwsh
""",
    )
    _write(data_dir / "shell.md", "# shell help\n```\nhelp\n```\n")
    _write(data_dir / "pwsh.md", "# list\n```\nGet-ChildItem\n```\n")

    with pytest.raises(HierarchyFormatError, match="not allowed; rename.*shell"):
        HierarchyManager(data_dir)


def test_hierarchy_manager_maps_only_leaf_documents(tmp_path: Path) -> None:
    _write(
        tmp_path / "root.yaml",
        """root:
  - shell:
    - pwsh
""",
    )
    _write(tmp_path / "_shell.md", "# private note\n```\nignored\n```\n")
    _write(tmp_path / "pwsh.md", "# list\n```\nGet-ChildItem\n```\n")

    manager = HierarchyManager(tmp_path)

    assert manager.get_mapped_document_names() == ["pwsh"]
    assert manager.get_active_document_names() == ["pwsh"]
    assert manager.is_leaf_node("shell") is False
    assert manager.is_leaf_node("pwsh") is True
