"""Main QuickType application - background daemon with GUI hotkey trigger."""

from typing import List, Optional

from .config import SnippetManager
from .core import SnippetEngine, TextInserter
from .gui import SnippetSearchWindow
from .hotkey import HotkeyManager


class QuickTypeApp:
    """Main application - manages engine, hotkeys, and GUI."""

    def __init__(self, hotkey: str = "ctrl+shift+q"):
        """
        Initialize QuickTypeApp.

        Args:
            hotkey: Global hotkey to trigger snippet search (default: Ctrl+Shift+Q).
        """
        self.manager = SnippetManager()
        self.engine = SnippetEngine(self.manager)
        self.hotkey_manager = HotkeyManager(hotkey)
        self.gui_window: Optional[SnippetSearchWindow] = None
        self.is_running = False

        # Set up text insertion callback
        self.engine.set_insert_callback(TextInserter.insert)

        # Create GUI window once (reuse for minimize-to-tray)
        self._init_gui_window()

    def _init_gui_window(self) -> None:
        """Initialize the GUI window (called once at startup)."""
        self.gui_window = SnippetSearchWindow(
            on_select=self._on_snippet_selected,
            on_close=self._on_window_hidden,
            snippets=self.engine.list_snippets(),
        )
        # Hide window initially (will show on hotkey)
        self.gui_window.root.withdraw()

    def _on_window_hidden(self) -> None:
        """Callback when search window is hidden."""
        pass  # Window is just hidden, not destroyed

    def start(self) -> None:
        """Start the application (register hotkey and start GUI mainloop)."""
        self.is_running = True

        print("QuickType started. Press Ctrl+Shift+Q to activate.")
        print("Press Ctrl+C to exit.")

        # Register hotkey callback (non-blocking)
        self.hotkey_manager.register(self._on_hotkey_pressed)

        # Start GUI mainloop (runs in main thread, handles all events)
        # This will block until the app is closed with Ctrl+C
        if self.gui_window:
            try:
                self.gui_window.start_mainloop()
            except KeyboardInterrupt:
                self.stop()

    def stop(self) -> None:
        """Stop the application."""
        self.is_running = False
        self.hotkey_manager.unregister()
        if self.gui_window:
            try:
                self.gui_window.destroy()
            except Exception:
                pass
        print("QuickType stopped.")

    def _on_hotkey_pressed(self) -> None:
        """Callback when hotkey is pressed - show search window."""
        if not self.gui_window:
            return

        try:
            # Update snippets list
            self.gui_window.update_snippets(self.engine.list_snippets())

            # Show the hidden window (or bring to front if already visible)
            self.gui_window.show()
        except Exception as e:
            print(f"Error showing search window: {e}")

    def _on_snippet_selected(self, snippet_name: str) -> None:
        """Callback when a snippet is selected - insert its content."""
        try:
            self.engine.insert_snippet(snippet_name)
        except Exception as e:
            print(f"Error inserting snippet: {e}")

    def add_snippet(self, name: str, content: str, tags: Optional[list] = None) -> None:
        """Add a snippet to the manager."""
        self.engine.add_snippet(name, content, tags=tags)

    def remove_snippet(self, name: str) -> bool:
        """Remove a snippet from the manager."""
        return self.engine.remove_snippet(name)

    def list_snippets(self):
        """List all available snippets."""
        return self.engine.list_snippets()
