from pathlib import Path

from quicktype.core import SnippetEngine
from quicktype.SnippetManager import SnippetManager


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _simple_note(title: str, command: str) -> str:
    return f"# {title}\n```\n{command}\n```\n"


def test_snippet_manager_loads_all_markdowns_and_composes_active_pool(tmp_path: Path) -> None:
    _write(
        tmp_path / "root.yaml",
        """root:
  - parent:
    - leaf_a
    - leaf_b
""",
    )

    _write(tmp_path / "parent.md", _simple_note("parent help", "echo parent"))
    _write(tmp_path / "leaf_a.md", _simple_note("leaf a", "echo a"))
    _write(tmp_path / "leaf_b.md", _simple_note("leaf b", "echo b"))
    _write(tmp_path / "orphan.md", _simple_note("orphan", "echo orphan"))

    manager = SnippetManager(data_dir=tmp_path)

    all_sources = sorted({snippet.source for snippet in manager.list_all_snippets()})
    assert all_sources == ["leaf_a", "leaf_b", "orphan", "parent"]

    assert manager.active_source_names() == ["parent", "leaf_a", "leaf_b"]

    active_names = sorted(snippet.name for snippet in manager.list_snippets())
    assert active_names == ["leaf a", "leaf b", "parent help"]


def test_subtree_toggle_recomposes_search_pool(tmp_path: Path) -> None:
    _write(
        tmp_path / "root.yaml",
        """root:
  - windbg:
    - pagefault
  - shell:
    - pwsh
""",
    )

    _write(tmp_path / "windbg.md", _simple_note("bugcheck", "!analyze -v"))
    _write(tmp_path / "pagefault.md", _simple_note("pf", "!gpagefault"))
    _write(tmp_path / "shell.md", _simple_note("shell", "echo shell"))
    _write(tmp_path / "pwsh.md", _simple_note("dir", "Get-ChildItem"))

    manager = SnippetManager(data_dir=tmp_path)

    manager.disable_subtree("windbg")
    assert manager.active_source_names() == ["shell", "pwsh"]
    assert sorted(snippet.name for snippet in manager.list_snippets()) == ["dir", "shell"]

    manager.set_subtree_enabled("windbg", True)
    assert manager.active_source_names() == ["windbg", "pagefault", "shell", "pwsh"]

    manager.disable_subtree("root")
    assert manager.list_snippets() == []

    manager.enable_all_subtrees()
    assert sorted(snippet.name for snippet in manager.list_snippets()) == [
        "bugcheck",
        "dir",
        "pf",
        "shell",
    ]


def test_add_snippet_appends_parser_compatible_markdown(tmp_path: Path) -> None:
    _write(
        tmp_path / "root.yaml",
        """root:
  - notes
""",
    )
    _write(tmp_path / "notes.md", _simple_note("existing", "echo existing"))

    manager = SnippetManager(data_dir=tmp_path)
    manager.add_snippet(
        name="new item",
        description="short description",
        payload="echo hello",
        source="notes",
    )

    content = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "# new item" in content
    assert "## short description" in content
    assert "```\necho hello\n```" in content

    reloaded = SnippetManager(data_dir=tmp_path)
    names = sorted(snippet.name for snippet in reloaded.list_snippets())
    assert names == ["existing", "new item"]


def test_remove_is_not_supported_in_engine(tmp_path: Path) -> None:
    _write(
        tmp_path / "root.yaml",
        """root:
  - notes
""",
    )
    _write(tmp_path / "notes.md", _simple_note("existing", "echo existing"))

    manager = SnippetManager(data_dir=tmp_path)
    engine = SnippetEngine(manager)
    assert engine.remove_snippet("existing") is False
