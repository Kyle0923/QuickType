"""Main QuickType application - background daemon with GUI hotkey trigger."""

from typing import List, Optional

from .SnippetManager import SnippetManager
from .core import SnippetEngine, TextInserter
from .gui import SnippetSearchWindow
from .hotkey import HotkeyManager


class QuickTypeApp:
    """Main application - manages engine, hotkeys, and GUI."""

    def __init__(self, hotkey: str):
        """
        Initialize QuickTypeApp.

        Args:
            hotkey: Global hotkey to trigger snippet search.
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
            hotkey=self.hotkey_manager.hotkey,
            on_hotkey_change=self.update_hotkey,
            on_exit=self.quit,
        )
        # Hide window initially (will show on hotkey)
        self.gui_window.root.withdraw()

    def _on_window_hidden(self) -> None:
        """Callback when search window is hidden."""
        pass  # Window is just hidden, not destroyed

    def start(self) -> None:
        """Start the application (register hotkey and start GUI mainloop)."""
        self.is_running = True

        print(f"QuickType started. Press {self.hotkey_manager.hotkey} to activate.")
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

    def quit(self) -> None:
        """Exit the app completely from the UI."""
        self.stop()
        raise SystemExit(0)

    def _on_hotkey_pressed(self) -> None:
        """Callback when hotkey is pressed from the global listener thread."""
        if not self.gui_window:
            return

        try:
            # Marshal UI work onto the Tk mainloop thread for stable focus behavior.
            self.gui_window.root.after(0, self._handle_hotkey_on_ui_thread)
        except Exception as e:
            print(f"Error showing search window: {e}")

    def _handle_hotkey_on_ui_thread(self) -> None:
        """Toggle window visibility from the Tk UI thread."""
        if not self.gui_window:
            return

        if self.gui_window.is_visible():
            if self.gui_window.is_foreground():
                self.gui_window.hide()
            else:
                self.gui_window.bring_to_front()
            return

        # Update snippets list before showing.
        self.gui_window.update_snippets(self.engine.list_snippets())
        self.gui_window.show()

    def update_hotkey(self, hotkey: str) -> None:
        """Update the global hotkey binding from the Settings menu."""
        try:
            self.hotkey_manager.set_hotkey(hotkey, self._on_hotkey_pressed)
            if self.gui_window:
                self.gui_window.update_hotkey(hotkey)
        except Exception as e:
            print(f"Error updating hotkey: {e}")

    def _on_snippet_selected(self, final_text: str, mode: str) -> None:
        """Callback when a snippet is selected - insert edited final content."""
        try:
            if mode == "type":
                TextInserter.insert(final_text)
            else:
                TextInserter.paste(final_text)
        except Exception as e:
            print(f"Error inserting snippet: {e}")

    def add_snippet(
        self,
        name: str,
        payload: str,
        source: str,
        description: Optional[str] = None,
    ) -> None:
        """Add a snippet to the manager."""
        self.engine.add_snippet(
            name=name,
            payload=payload,
            source=source,
            description=description,
        )

    def remove_snippet(self, name: str) -> bool:
        """Remove is currently not supported."""
        _ = name
        return False

    def list_snippets(self):
        """List all available snippets."""
        return self.engine.list_snippets()
