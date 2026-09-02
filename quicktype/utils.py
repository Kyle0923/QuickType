"""Shared utilities for QuickType - OS detection, config paths, and helpers."""

import sys
import platform
from pathlib import Path
from typing import Literal


def get_platform() -> Literal["windows", "darwin", "linux"]:
    """
    Detect the current operating system.

    Returns:
        A platform identifier: "windows", "darwin" (macOS), or "linux".
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "darwin"
    else:
        return "linux"


def get_config_dir() -> Path:
    r"""
    Get the platform-standard configuration directory for QuickType.

    Returns:
        Path to QuickType config directory:
        - Windows: %APPDATA%\quicktype
        - macOS/Linux: ~/.config/quicktype
    """
    platform_name = get_platform()

    if platform_name == "windows":
        appdata = Path.home() / "AppData" / "Roaming"
        config_dir = appdata / "quicktype"
    else:  # macOS and Linux
        config_dir = Path.home() / ".config" / "quicktype"

    return config_dir


def ensure_config_dir() -> Path:
    """
    Ensure the config directory exists, creating it if necessary.

    Returns:
        Path to QuickType config directory.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
