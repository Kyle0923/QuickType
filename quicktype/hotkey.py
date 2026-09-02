"""Hotkey management for QuickType - global keyboard shortcuts."""

from typing import Callable, Optional

import keyboard


class HotkeyManager:
    """Manages global hotkey registration and callbacks."""

    def __init__(self, hotkey: str):
        """
        Initialize HotkeyManager.

        Args:
            hotkey: Hotkey combination (e.g., "ctrl+shift+space", "alt+space").
        """
        self.hotkey = hotkey
        self.callback: Optional[Callable[[], None]] = None
        self.is_registered = False

    def set_hotkey(self, hotkey: str, callback: Optional[Callable[[], None]] = None) -> None:
        """Update the registered hotkey while preserving the current callback."""
        normalized = hotkey.strip()
        if not normalized:
            raise ValueError("Hotkey cannot be empty.")

        if callback is not None:
            self.callback = callback

        if self.is_registered and self.hotkey != normalized:
            self.unregister()

        self.hotkey = normalized

        if self.callback is not None and not self.is_registered:
            self.register(self.callback)

    def register(self, callback: Callable[[], None]) -> None:
        """
        Register a callback for the hotkey.

        Note: This is non-blocking. The callback will be invoked when the hotkey is pressed.

        Args:
            callback: Function to call when hotkey is pressed.

        Raises:
            RuntimeError: If hotkey registration fails.
        """
        self.callback = callback
        try:
            keyboard.add_hotkey(self.hotkey, callback, suppress=True)
            self.is_registered = True
        except Exception as e:
            raise RuntimeError(f"Failed to register hotkey '{self.hotkey}': {e}")

    def unregister(self) -> None:
        """Unregister the hotkey."""
        if self.is_registered:
            try:
                keyboard.remove_hotkey(self.hotkey)
                self.is_registered = False
            except Exception as e:
                print(f"Warning: Failed to unregister hotkey: {e}")
