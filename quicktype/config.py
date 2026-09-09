"""Shared configuration constants for QuickType."""

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = _REPO_ROOT / ".data"
DEFAULT_HOTKEY = "ctrl+shift+q"
DEFAULT_WINDOW_GEOMETRY = "700x760"
DEFAULT_WINDOW_MIN_SIZE = (700, 700)
DEFAULT_HIERARCHY_ROOT_FILE = "root.yaml"


__all__ = [
	"DEFAULT_DATA_DIR",
	"DEFAULT_HOTKEY",
	"DEFAULT_WINDOW_GEOMETRY",
	"DEFAULT_WINDOW_MIN_SIZE",
	"DEFAULT_HIERARCHY_ROOT_FILE",
]
