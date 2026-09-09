_FZF_ESCAPE_MAP = {
    "!": "\uE000",
    "'": "\uE001",
    "^": "\uE002",
    "$": "\uE003",
    "|": "\uE004",
}

_FZF_UNESCAPE_MAP = {v: k for k, v in _FZF_ESCAPE_MAP.items()}


def fzf_escape(text: str) -> str:
    """Escape fzf extended-search operators using single Unicode characters."""
    for char, replacement in _FZF_ESCAPE_MAP.items():
        text = text.replace(char, replacement)
    return text


def fzf_unescape(text: str) -> str:
    """Restore fzf extended-search operators."""
    for replacement, char in _FZF_UNESCAPE_MAP.items():
        text = text.replace(replacement, char)
    return text

