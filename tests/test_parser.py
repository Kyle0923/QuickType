"""Test parser functionality and strict format validation."""

from pathlib import Path
import pytest
from quicktype.config import DEFAULT_DATA_DIR
from quicktype.snippet import FormatError, parse_data_directory, parse_markdown_file


def test_parser_excludes_blockquotes():
    """Verify blockquotes are excluded from searchable text."""
    data_dir = DEFAULT_DATA_DIR
    sections = parse_data_directory(data_dir)

    # Test bugcheck section
    bugcheck = [s for s in sections.get('windbg', [])
                if s.name == 'bugcheck'][0]

    # Should match: name, description, code content
    assert 'bugcheck' in bugcheck.searchable_text
    assert 'decode' in bugcheck.searchable_text
    assert '!analyze' in bugcheck.searchable_text
    assert '!gs' in bugcheck.searchable_text

    # Should NOT match: blockquote text
    assert 'Analyzes a bugcheck' not in bugcheck.searchable_text
    assert 'displays detailed information' not in bugcheck.searchable_text
    assert bugcheck.location.endswith('windbg.md:1')

    print("✓ Blockquotes correctly excluded from search")


def test_parser_extracts_all_sections():
    """Verify all sections are extracted."""
    data_dir = DEFAULT_DATA_DIR
    sections = parse_data_directory(data_dir)

    windbg_sections = sections.get('windbg', [])
    assert len(windbg_sections) == 4, f"Expected 4 sections, got {len(windbg_sections)}"

    names = [s.name for s in windbg_sections]
    assert 'bugcheck' in names
    assert 'start TCP server' in names
    assert 'start PIPE server' in names
    assert 'Some Cmd that has a long long cmd' in names

    print("✓ All 4 sections extracted correctly")


def test_parser_preserves_placeholders():
    """Verify placeholders are preserved in content."""
    data_dir = DEFAULT_DATA_DIR
    sections = parse_data_directory(data_dir)

    tcp_section = [s for s in sections.get('windbg', [])
                   if s.description == 'open a debug server'][0]

    assert '{{port_num:5050}}' in tcp_section.payload

    print("✓ Placeholders preserved in content")


def test_parser_extracts_quote_into_snippet_note():
    """Verify markdown blockquote text is stored for note tooltips."""
    data_dir = DEFAULT_DATA_DIR
    sections = parse_data_directory(data_dir)

    bugcheck = [s for s in sections.get('windbg', []) if s.name == 'bugcheck'][0]
    tcp_section = [s for s in sections.get('windbg', []) if s.name == 'start TCP server'][0]

    assert bugcheck.note == 'Analyzes a bugcheck code and displays detailed information'
    assert tcp_section.note == 'Opens a debugging server on the specified port\nand tell me more'


def test_parser_rejects_missing_code_block():
    """Verify parser rejects sections with missing code block."""
    invalid_md = Path(__file__).parent / 'test_invalid_no_code.md'
    invalid_md.write_text("""# test
## subsection
> comment
no code block here
""", encoding='utf-8')

    try:
        with pytest.raises(FormatError, match="No code block"):
            parse_markdown_file(invalid_md)
        print("✓ Correctly rejects missing code block")
    finally:
        invalid_md.unlink()


def test_parser_rejects_multiple_code_blocks():
    """Verify parser rejects sections with multiple code blocks."""
    invalid_md = Path(__file__).parent / 'test_invalid_multi_code.md'
    invalid_md.write_text("""# test
## subsection
> comment
```
code1
```
```
code2
```
""", encoding='utf-8')

    try:
        with pytest.raises(FormatError, match="found 2"):
            parse_markdown_file(invalid_md)
        print("✓ Correctly rejects multiple code blocks")
    finally:
        invalid_md.unlink()


def test_parser_rejects_multiple_quote_blocks():
    """Verify parser rejects sections with multiple separate quote blocks."""
    invalid_md = Path(__file__).parent / 'test_invalid_multi_quote.md'
    invalid_md.write_text("""# test
## subsection
> quote1
some text
> quote2
```
code
```
""", encoding='utf-8')

    try:
        with pytest.raises(FormatError, match="found 2"):
            parse_markdown_file(invalid_md)
        print("✓ Correctly rejects multiple quote blocks")
    finally:
        invalid_md.unlink()


def test_parser_accepts_multiline_quote():
    """Verify parser accepts multi-line contiguous quote block."""
    valid_md = Path(__file__).parent / 'test_valid_multiline_quote.md'
    valid_md.write_text("""# test
## subsection
> line 1
> line 2
> line 3
```
code
```
""", encoding='utf-8')

    try:
        sections = parse_markdown_file(valid_md)
        assert len(sections) == 1
        assert sections[0].payload == "code"
        print("✓ Correctly accepts multi-line quote block")
    finally:
        valid_md.unlink()


def test_parser_rejects_multiple_h2_descriptions_per_h1():
    """Verify parser rejects more than one H2 under the same H1 section."""
    invalid_md = Path(__file__).parent / 'test_invalid_multi_h2.md'
    invalid_md.write_text("""# test
## first description
```
code1
```
## second description
```
code2
```
""", encoding='utf-8')

    try:
        with pytest.raises(FormatError, match="at most one H2"):
            parse_markdown_file(invalid_md)
        print("✓ Correctly rejects multiple H2 descriptions under one H1")
    finally:
        invalid_md.unlink()


if __name__ == "__main__":
    test_parser_excludes_blockquotes()
    test_parser_extracts_all_sections()
    test_parser_preserves_placeholders()
    test_parser_extracts_quote_into_snippet_note()
    test_parser_rejects_missing_code_block()
    test_parser_rejects_multiple_code_blocks()
    test_parser_rejects_multiple_quote_blocks()
    test_parser_accepts_multiline_quote()
    print("\n✅ All parser tests passed!")
