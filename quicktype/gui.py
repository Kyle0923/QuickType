"""GUI components for QuickType - search window and snippet display."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from .SnippetManager import Snippet
from .core import FuzzyMatcher


class SnippetSearchWindow:
    """Main GUI window for searching and selecting snippets."""

    def __init__(
        self,
        on_select: Callable[[str, str], None],
        on_close: Callable[[], None],
        snippets: Optional[List[Snippet]] = None,
        hotkey: str = "ctrl+shift+space",
        on_hotkey_change: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
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
        self.hotkey = hotkey
        self.on_hotkey_change = on_hotkey_change
        self.on_exit = on_exit
        self.fuzzy_matcher = FuzzyMatcher(threshold=60)

        self.root = tk.Tk()
        self.root.title("QuickType Search")
        self.root.geometry("640x760")
        self.root.minsize(620, 700)
        self.root.attributes("-topmost", True)  # Keep window on top

        # Handle window close - hide instead of destroy
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self._setup_menu()

        # Search input
        search_frame = ttk.Frame(self.root)
        search_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_input)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind("<Up>", self._on_arrow_key)
        self.search_entry.bind("<Down>", self._on_arrow_key)
        self.search_entry.bind("<Return>", self._on_enter)
        self.search_entry.bind("<KP_Enter>", self._on_enter)
        self.search_entry.bind("<Alt-Return>", self._on_alt_enter)
        self.search_entry.bind("<Alt-KP_Enter>", self._on_alt_enter)
        self.search_entry.bind("<Control-w>", self._on_ctrl_w)
        self.search_entry.bind("<Control-d>", self._on_ctrl_d)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Control-d>", self._on_ctrl_d)
        self.search_entry.focus_set()

        # Snippet list
        list_frame = ttk.Frame(self.root)
        list_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Notes:").pack(anchor=tk.W)

        # Listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.snippet_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, height=15
        )
        self.snippet_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.snippet_listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.snippet_listbox.bind("<Return>", self._on_enter)
        self.snippet_listbox.bind("<KP_Enter>", self._on_enter)
        self.snippet_listbox.bind("<Alt-Return>", self._on_alt_enter)
        self.snippet_listbox.bind("<Alt-KP_Enter>", self._on_alt_enter)
        scrollbar.config(command=self.snippet_listbox.yview)

        # Content preview
        preview_frame = ttk.LabelFrame(self.root, text="Preview")
        preview_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.preview_text = tk.Text(preview_frame, height=6, width=50, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        self.preview_text.config(state=tk.DISABLED)

        # Editable final payload (allows replacing placeholders like {{variable}})
        final_frame = ttk.LabelFrame(self.root, text="Final")
        final_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.final_text = tk.Text(final_frame, height=6, width=50, wrap=tk.WORD)
        self.final_text.pack(fill=tk.BOTH, expand=True)
        self.final_text.bind("<Return>", self._on_enter)
        self.final_text.bind("<KP_Enter>", self._on_enter)
        self.final_text.bind("<Alt-Return>", self._on_alt_enter)
        self.final_text.bind("<Alt-KP_Enter>", self._on_alt_enter)
        self.final_text.bind("<Shift-Return>", lambda event: None)
        self.final_text.bind("<Shift-KP_Enter>", lambda event: None)

        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        # Update list with all snippets
        self._update_snippet_list(self.snippets)

    def _setup_menu(self) -> None:
        """Create the top-level menu bar with application settings."""
        menubar = tk.Menu(self.root)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Hotkey...", command=self._open_hotkey_dialog)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        menubar.add_command(label="Exit", command=self._request_exit)
        self.root.config(menu=menubar)

    def _request_exit(self) -> None:
        """Request an application exit from the menu."""
        if self.on_exit:
            self.on_exit()

    def _open_hotkey_dialog(self) -> None:
        """Open a small modal dialog for editing the global hotkey."""
        dialog = tk.Toplevel(self.root)
        dialog.title("QuickType Settings")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Hotkey:").grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        hotkey_var = tk.StringVar(value=self.hotkey)
        entry = ttk.Entry(dialog, textvariable=hotkey_var, width=25)
        entry.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ew")
        entry.focus_set()

        def save_hotkey() -> None:
            new_hotkey = hotkey_var.get().strip()
            if not new_hotkey:
                return
            self.hotkey = new_hotkey
            if self.on_hotkey_change:
                self.on_hotkey_change(new_hotkey)
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        ttk.Button(button_row, text="Save", command=save_hotkey).pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=(5, 10))

        dialog.columnconfigure(1, weight=1)

    def update_hotkey(self, hotkey: str) -> None:
        """Keep the current hotkey value in sync with the app."""
        self.hotkey = hotkey

    def _on_search_input(self, *args) -> None:
        """Handle search input changes."""
        query = self.search_var.get()

        if query:
            self.filtered_snippets = self.fuzzy_matcher.search(query, self.snippets)
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

    def _on_arrow_key(self, event: tk.Event) -> str:
        """Move the current snippet selection with the keyboard arrow keys."""
        if not self.filtered_snippets:
            return "break"

        offset = -1 if event.keysym == "Up" else 1
        self._move_selection(offset)
        return "break"

    def _move_selection(self, offset: int) -> None:
        """Move the selected snippet up or down with wrap-around."""
        if not self.filtered_snippets:
            return

        next_index = (self.selected_index + offset) % len(self.filtered_snippets)
        self.selected_index = next_index
        self.snippet_listbox.selection_clear(0, tk.END)
        self.snippet_listbox.selection_set(next_index)
        self.snippet_listbox.activate(next_index)
        self._update_preview(self.filtered_snippets[next_index])

    def _on_ctrl_w(self, event: tk.Event) -> str:
        """Delete the previous word and any extra spaces before the cursor."""
        current = self.search_var.get()
        cursor_index = self.search_entry.index(tk.INSERT)
        if cursor_index <= 0:
            return "break"

        prefix = current[:cursor_index]
        suffix = current[cursor_index:]
        trimmed_prefix = prefix.rstrip()

        if not trimmed_prefix:
            self.search_var.set(suffix)
            self.search_entry.icursor(0)
            return "break"

        last_space_index = trimmed_prefix.rfind(" ")
        if last_space_index == -1:
            new_prefix = ""
        else:
            new_prefix = trimmed_prefix[:last_space_index].rstrip()

        if suffix and suffix[0] != " " and new_prefix:
            new_prefix = new_prefix + " "

        new_text = new_prefix + suffix
        self.search_var.set(new_text)
        self.search_entry.icursor(len(new_prefix))
        return "break"

    def _on_ctrl_d(self, event: tk.Event) -> str:
        """Clear the search box and reset the snippet list."""
        self.search_var.set("")
        self.search_entry.icursor(0)
        return "break"

    def _on_escape(self, event: tk.Event) -> str:
        """Hide the search window."""
        self._hide_window()
        return "break"

    def _update_preview(self, snippet: Snippet) -> None:
        """Update the content preview for a snippet."""
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, snippet.payload)
        self.preview_text.config(state=tk.DISABLED)

        self.final_text.delete(1.0, tk.END)
        self.final_text.insert(tk.END, snippet.payload)

    def _get_final_text(self) -> str:
        """Return editable final payload text without the trailing Tk newline."""
        return self.final_text.get("1.0", tk.END).rstrip("\n")

    def _on_snippet_insert(self, event: tk.Event) -> None:
        """Handle Return key to insert selected snippet."""
        self._insert_selected()

    def _on_enter(self, event: tk.Event) -> str:
        """Insert using paste mode."""
        self._insert_selected(mode="paste")
        return "break"

    def _on_alt_enter(self, event: tk.Event) -> str:
        """Insert using keyboard typing mode."""
        self._insert_selected(mode="type")
        return "break"

    def _insert_selected(self, mode: str = "paste") -> None:
        """Insert the selected snippet."""
        if self.selected_index < len(self.filtered_snippets):
            final_text = self._get_final_text()
            self._hide_window()
            self.root.after(80, lambda: self.on_select(final_text, mode))

    def _hide_window(self) -> None:
        """Hide the window (minimize to tray)."""
        try:
            self.root.withdraw()
        except Exception:
            pass

    def hide(self) -> None:
        """Public wrapper to hide the window."""
        self._hide_window()

    def is_visible(self) -> bool:
        """Return True when the window is currently visible."""
        try:
            return self.root.state() != "withdrawn"
        except Exception:
            return False

    def is_foreground(self) -> bool:
        """Return True when this window currently owns focus."""
        try:
            focused_widget = self.root.focus_displayof()
            if focused_widget is None:
                return False
            return focused_widget.winfo_toplevel() == self.root
        except Exception:
            return False

    def show(self) -> None:
        """Display the window (show hidden window, don't create new mainloop)."""
        try:
            # Clear search for fresh start
            self.search_var.set("")
            self._update_snippet_list(self.snippets)

            self._center_window()
            self._raise_and_focus()
        except Exception as e:
            print(f"Error showing window: {e}")

    def bring_to_front(self) -> None:
        """Bring a visible-but-unfocused window back to the foreground."""
        try:
            # Mimic manual hide/show behavior that reliably restores focus.
            self.root.withdraw()
            self.root.after(10, self._raise_and_focus)
        except Exception as e:
            print(f"Error focusing window: {e}")

    def _raise_and_focus(self) -> None:
        """Raise, deiconify and focus the window."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        # Delay refocus to give the OS time to settle foreground ownership.
        self.root.after(120, self._focus_search_entry)
        self.root.after(220, self._focus_search_entry)

    def _center_window(self) -> None:
        """Center the window on the active screen."""
        self.root.update_idletasks()

        width = self.root.winfo_width()
        height = self.root.winfo_height()

        # Fallback when the withdrawn window reports a minimal size.
        if width <= 1 or height <= 1:
            width = self.root.winfo_reqwidth()
            height = self.root.winfo_reqheight()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _focus_search_entry(self) -> None:
        """Focus and place the cursor in the search entry."""
        if hasattr(self, "search_entry"):
            self.search_entry.focus_force()
            self.search_entry.icursor(tk.END)
            self.root.update_idletasks()

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
