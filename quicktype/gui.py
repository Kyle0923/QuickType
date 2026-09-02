"""GUI components for QuickType - search window and snippet display."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from .config import Snippet


class SnippetSearchWindow:
    """Main GUI window for searching and selecting snippets."""

    def __init__(
        self,
        on_select: Callable[[str], None],
        on_close: Callable[[], None],
        snippets: Optional[List[Snippet]] = None,
    ):
        """
        Initialize the snippet search window.

        Args:
            on_select: Callback when a snippet is selected.
            on_close: Callback when window is closed.
            snippets: Initial list of snippets to display.
        """
        self.on_select = on_select
        self.on_close = on_close
        self.snippets = snippets or []
        self.filtered_snippets: List[Snippet] = []
        self.selected_index = 0

        self.root = tk.Tk()
        self.root.title("QuickType Search")
        self.root.geometry("500x400")
        self.root.attributes("-topmost", True)  # Keep window on top

        # Handle window close - hide instead of destroy
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Search input
        search_frame = ttk.Frame(self.root)
        search_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_input)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.focus()

        # Snippet list
        list_frame = ttk.Frame(self.root)
        list_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Snippets:").pack(anchor=tk.W)

        # Listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.snippet_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, height=15
        )
        self.snippet_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.snippet_listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.snippet_listbox.bind("<Return>", self._on_snippet_insert)
        scrollbar.config(command=self.snippet_listbox.yview)

        # Content preview
        preview_frame = ttk.LabelFrame(self.root, text="Preview")
        preview_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.preview_text = tk.Text(preview_frame, height=6, width=50, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        self.preview_text.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Insert", command=self._insert_selected).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Close", command=self._hide_window).pack(
            side=tk.LEFT, padx=5
        )

        # Update list with all snippets
        self._update_snippet_list(self.snippets)

    def _on_search_input(self, *args) -> None:
        """Handle search input changes."""
        query = self.search_var.get()

        # Filter snippets (simple substring match for now)
        if query:
            self.filtered_snippets = [
                s
                for s in self.snippets
                if query.lower() in s.name.lower() or query.lower() in s.content.lower()
            ]
        else:
            self.filtered_snippets = self.snippets

        self._update_snippet_list(self.filtered_snippets)

    def _update_snippet_list(self, snippets: List[Snippet]) -> None:
        """Update the listbox with snippets."""
        self.snippet_listbox.delete(0, tk.END)
        for snippet in snippets:
            # Truncate long names for display
            display_text = (
                snippet.name
                if len(snippet.name) < 50
                else snippet.name[:47] + "..."
            )
            self.snippet_listbox.insert(tk.END, display_text)

        if snippets:
            self.snippet_listbox.selection_set(0)
            self.selected_index = 0
            self._update_preview(snippets[0])

    def _on_list_select(self, event: tk.Event) -> None:
        """Handle snippet selection in listbox."""
        selection = self.snippet_listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            if self.selected_index < len(self.filtered_snippets):
                self._update_preview(self.filtered_snippets[self.selected_index])

    def _update_preview(self, snippet: Snippet) -> None:
        """Update the content preview for a snippet."""
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, snippet.content)
        self.preview_text.config(state=tk.DISABLED)

    def _on_snippet_insert(self, event: tk.Event) -> None:
        """Handle Return key to insert selected snippet."""
        self._insert_selected()

    def _insert_selected(self) -> None:
        """Insert the selected snippet."""
        if self.selected_index < len(self.filtered_snippets):
            snippet = self.filtered_snippets[self.selected_index]
            self.on_select(snippet.name)
            self._hide_window()

    def _hide_window(self) -> None:
        """Hide the window (minimize to tray)."""
        try:
            self.root.withdraw()
        except Exception:
            pass

    def show(self) -> None:
        """Display the window (show hidden window, don't create new mainloop)."""
        try:
            # Clear search for fresh start
            self.search_var.set("")
            self._update_snippet_list(self.snippets)

            # Show and focus window
            self.root.deiconify()
            self.root.lift()
            self.root.focus()
        except Exception as e:
            print(f"Error showing window: {e}")

    def start_mainloop(self) -> None:
        """Start the Tkinter mainloop (call once from app.start())."""
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"GUI mainloop error: {e}")

    def destroy(self) -> None:
        """Properly destroy the window and clean up."""
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def update_snippets(self, snippets: List[Snippet]) -> None:
        """Update the list of available snippets."""
        self.snippets = snippets
        self._update_snippet_list(snippets)
