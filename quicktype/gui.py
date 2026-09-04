"""GUI components for QuickType - search window and snippet display."""

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple

from .SnippetManager import Snippet
from .config import DEFAULT_HOTKEY, DEFAULT_WINDOW_GEOMETRY, DEFAULT_WINDOW_MIN_SIZE
from .core import FuzzyMatcher
from .icons import create_app_icon_image


class SnippetSearchWindow:
    """Main GUI window for searching and selecting snippets."""

    LIST_ITEM_LEFT_PAD = "  "
    HIERARCHY_ROOT_ID = "__navigation_root__"
    HIERARCHY_ROOT_LABEL = "root"
    PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.\-\s]+?)\s*\}\}")

    def __init__(
        self,
        on_select: Callable[[str, str], None],
        on_close: Callable[[], None],
        snippets: Optional[List[Snippet]] = None,
        hotkey: str = DEFAULT_HOTKEY,
        on_hotkey_change: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        hierarchy_rows_provider: Optional[Callable[[], List[Tuple[str, Optional[str], bool]]]] = None,
        on_hierarchy_toggle: Optional[Callable[[str, bool], List[Snippet]]] = None,
        on_hierarchy_open: Optional[Callable[[str], None]] = None,
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
        self.hierarchy_rows_provider = hierarchy_rows_provider
        self.on_hierarchy_toggle = on_hierarchy_toggle
        self.on_hierarchy_open = on_hierarchy_open
        self.fuzzy_matcher = FuzzyMatcher(threshold=60)
        self._final_original_text = ""
        self._placeholder_names: List[str] = []
        self._variable_values: Dict[str, str] = {}
        self._variable_vars: Dict[str, tk.StringVar] = {}
        self._pending_hierarchy_toggle_id = None
        self._pending_hierarchy_item: Optional[str] = None
        self._hierarchy_tree_initialized = False

        self.root = tk.Tk()
        self.root.title("QuickType Search")
        self.root.geometry(DEFAULT_WINDOW_GEOMETRY)
        self.root.minsize(*DEFAULT_WINDOW_MIN_SIZE)
        self.root.attributes("-topmost", True)  # Keep window on top
        self._set_titlebar_icon()

        # Handle window close - hide instead of destroy
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        self._setup_ui()

    def _set_titlebar_icon(self) -> None:
        """Apply the shared app icon to the native window title bar."""
        try:
            from PIL import ImageTk

            image = create_app_icon_image(size=64)
            self._titlebar_icon = ImageTk.PhotoImage(image)
            self.root.iconphoto(True, self._titlebar_icon)
        except Exception:
            # Keep startup resilient if icon rendering is unavailable.
            pass

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self._setup_menu()

        # Search input
        search_frame = ttk.Frame(self.root)
        search_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_input)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
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

        # Content area: sidebar + main panels (Notes / Preview / Final)
        content_frame = ttk.Frame(self.root)
        content_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        content_split = tk.PanedWindow(
            content_frame,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            bd=0,
            relief=tk.FLAT,
        )
        content_split.pack(fill=tk.BOTH, expand=True)

        sidebar_frame = ttk.Frame(content_split, width=180)

        sidebar_split = tk.PanedWindow(
            sidebar_frame,
            orient=tk.VERTICAL,
            sashwidth=5,
            sashrelief=tk.RAISED,
            bd=0,
            relief=tk.FLAT,
        )
        sidebar_split.pack(fill=tk.BOTH, expand=True)

        hierarchy_frame = ttk.LabelFrame(sidebar_split, text="Navigation")

        hierarchy_scrollbar = ttk.Scrollbar(hierarchy_frame)
        hierarchy_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.hierarchy_tree = ttk.Treeview(
            hierarchy_frame,
            show="tree",
            selectmode="browse",
            yscrollcommand=hierarchy_scrollbar.set,
        )
        self.hierarchy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hierarchy_scrollbar.config(command=self.hierarchy_tree.yview)
        self.hierarchy_tree.bind("<Button-1>", self._on_hierarchy_click)
        self.hierarchy_tree.bind("<Double-1>", self._on_hierarchy_double_click)
        self.hierarchy_tree.bind("<space>", self._on_hierarchy_keyboard_toggle)
        self.hierarchy_tree.bind("<Return>", self._on_hierarchy_keyboard_toggle)

        variables_frame = ttk.LabelFrame(sidebar_split, text="Variables")
        variables_frame.rowconfigure(0, weight=1)
        variables_frame.columnconfigure(0, weight=1)

        self.variable_canvas = tk.Canvas(variables_frame, borderwidth=0, highlightthickness=0)
        self.variable_canvas.grid(row=0, column=0, sticky="nsew")

        variable_scrollbar = ttk.Scrollbar(
            variables_frame,
            orient=tk.VERTICAL,
            command=self.variable_canvas.yview,
        )
        variable_scrollbar.grid(row=0, column=1, sticky="ns")
        self.variable_canvas.configure(yscrollcommand=variable_scrollbar.set)

        self.variable_container = ttk.Frame(self.variable_canvas)
        self.variable_window_id = self.variable_canvas.create_window(
            (0, 0),
            window=self.variable_container,
            anchor="nw",
        )
        self.variable_container.bind("<Configure>", self._on_variable_container_configure)
        self.variable_canvas.bind("<Configure>", self._on_variable_canvas_configure)

        sidebar_split.add(hierarchy_frame, minsize=180)
        sidebar_split.add(variables_frame, minsize=140)
        self.root.after(0, lambda: sidebar_split.sash_place(0, 1, 220))

        main_frame = ttk.Frame(content_split)

        content_split.add(sidebar_frame, minsize=140)
        content_split.add(main_frame, minsize=320)
        self.root.after(0, lambda: content_split.sash_place(0, 190, 1))

        # Snippet list
        list_frame = ttk.LabelFrame(main_frame, text="Notes")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        list_x_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        list_x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.snippet_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            xscrollcommand=list_x_scrollbar.set,
            height=15,
        )
        self.snippet_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.snippet_listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.snippet_listbox.bind("<Return>", self._on_enter)
        self.snippet_listbox.bind("<KP_Enter>", self._on_enter)
        self.snippet_listbox.bind("<Alt-Return>", self._on_alt_enter)
        self.snippet_listbox.bind("<Alt-KP_Enter>", self._on_alt_enter)
        scrollbar.config(command=self.snippet_listbox.yview)
        list_x_scrollbar.config(command=self.snippet_listbox.xview)

        # Content preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        preview_y_scrollbar = ttk.Scrollbar(preview_frame)
        preview_y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        preview_x_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL)
        preview_x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.preview_text = tk.Text(
            preview_frame,
            height=6,
            width=50,
            wrap=tk.NONE,
            padx=3,
            xscrollcommand=preview_x_scrollbar.set,
            yscrollcommand=preview_y_scrollbar.set,
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        preview_x_scrollbar.config(command=self.preview_text.xview)
        preview_y_scrollbar.config(command=self.preview_text.yview)
        self.preview_text.config(state=tk.DISABLED)

        # Editable final payload (allows replacing placeholders like {{variable}})
        final_frame = ttk.LabelFrame(main_frame, text="Final")
        final_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        final_header = ttk.Frame(final_frame)
        final_header.pack(fill=tk.X)

        tk.Button(
            final_header,
            text="Reset",
            width=6,
            fg="#000000",
            activeforeground="#666666",
            activebackground="#E0E0E0",
            font=("Segoe UI", 9, "bold"),
            relief=tk.RIDGE,
            bd=1,
            padx=2,
            pady=1,
            cursor="hand2",
            command=self._reset_final_text,
        ).pack(side=tk.LEFT, padx=(6, 0), pady=(0, 2))

        final_y_scrollbar = ttk.Scrollbar(final_frame)
        final_y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        final_x_scrollbar = ttk.Scrollbar(final_frame, orient=tk.HORIZONTAL)
        final_x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.final_text = tk.Text(
            final_frame,
            height=6,
            width=50,
            wrap=tk.NONE,
            undo=True,
            padx=3,
            xscrollcommand=final_x_scrollbar.set,
            yscrollcommand=final_y_scrollbar.set,
        )
        self.final_text.pack(fill=tk.BOTH, expand=True)
        final_x_scrollbar.config(command=self.final_text.xview)
        final_y_scrollbar.config(command=self.final_text.yview)
        self.final_text.bind("<Return>", self._on_enter)
        self.final_text.bind("<KP_Enter>", self._on_enter)
        self.final_text.bind("<Alt-Return>", self._on_alt_enter)
        self.final_text.bind("<Alt-KP_Enter>", self._on_alt_enter)
        self.final_text.bind("<Shift-Return>", lambda event: None)
        self.final_text.bind("<Shift-KP_Enter>", lambda event: None)
        self.final_text.bind("<Tab>", lambda e: e.widget.tk_focusNext().focus_set() or "break")

        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        # Update list with all snippets
        self._update_snippet_list(self.snippets)
        self._refresh_hierarchy_tree()

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
        self.filtered_snippets = snippets
        self.snippet_listbox.delete(0, tk.END)
        for snippet in snippets:
            display_name = snippet.name
            if snippet.description:
                display_name = f"{snippet.name} - {snippet.description}"
            self.snippet_listbox.insert(tk.END, f"{self.LIST_ITEM_LEFT_PAD}{display_name}")

        if snippets:
            self.snippet_listbox.selection_set(0)
            self.selected_index = 0
            self._update_preview(snippets[0])
        else:
            self.selected_index = 0
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.config(state=tk.DISABLED)
            self._final_original_text = ""
            self.final_text.delete(1.0, tk.END)
            self._render_variable_editor([])

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

        self._final_original_text = snippet.payload
        placeholders = self._extract_placeholders(self._final_original_text)
        self._render_variable_editor(placeholders)
        self._refresh_final_text_from_variables()

    def _reset_final_text(self) -> None:
        """Restore the editable final text to the last selected snippet payload."""
        for variable_var in self._variable_vars.values():
            variable_var.set("")
        self._refresh_final_text_from_variables()

    def _extract_placeholders(self, text: str) -> List[str]:
        """Extract unique placeholder names from {{name}} tokens in order."""
        ordered: List[str] = []
        seen = set()
        for match in self.PLACEHOLDER_PATTERN.finditer(text):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    def _replace_with_current_variables(self, text: str) -> str:
        """Replace placeholders with user-provided values when available."""

        def replace(match: re.Match) -> str:
            key = match.group(1).strip()
            value = self._variable_values.get(key, "")
            return value if value else match.group(0)

        return self.PLACEHOLDER_PATTERN.sub(replace, text)

    def _render_variable_editor(self, placeholders: List[str]) -> None:
        """Render variable entry rows based on placeholders in the selected snippet."""
        self._placeholder_names = placeholders
        self._variable_vars = {}

        for child in self.variable_container.winfo_children():
            child.destroy()

        if not placeholders:
            ttk.Label(
                self.variable_container,
                text="No placeholders in this snippet.",
            ).grid(row=0, column=0, padx=6, pady=6, sticky="w")
            return

        for row_index, placeholder in enumerate(placeholders):
            ttk.Label(
                self.variable_container,
                text=placeholder,
            ).grid(row=row_index, column=0, padx=(6, 4), pady=4, sticky="w")

            value_var = tk.StringVar(value=self._variable_values.get(placeholder, ""))
            value_var.trace_add("write", self._on_variable_change)
            entry = ttk.Entry(self.variable_container, textvariable=value_var, width=18)
            entry.grid(row=row_index, column=1, padx=(0, 6), pady=4, sticky="ew")
            self._variable_vars[placeholder] = value_var

        self.variable_container.columnconfigure(1, weight=1)

    def _on_variable_change(self, *args) -> None:
        """Track variable values and refresh final text after edits."""
        _ = args
        for name, variable_var in self._variable_vars.items():
            self._variable_values[name] = variable_var.get()
        self._refresh_final_text_from_variables()

    def _refresh_final_text_from_variables(self) -> None:
        """Render final text from template payload and current variable values."""
        rendered = self._replace_with_current_variables(self._final_original_text)
        self.final_text.delete(1.0, tk.END)
        self.final_text.insert(tk.END, rendered)

    def _on_variable_container_configure(self, event: tk.Event) -> None:
        """Keep variable canvas scroll region in sync with dynamic row count."""
        _ = event
        self.variable_canvas.configure(scrollregion=self.variable_canvas.bbox("all"))

    def _on_variable_canvas_configure(self, event: tk.Event) -> None:
        """Stretch variable editor width to the sidebar width."""
        self.variable_canvas.itemconfigure(self.variable_window_id, width=event.width)

    def _refresh_hierarchy_tree(self) -> None:
        """Rebuild the hierarchy tree section from provider data."""
        expanded_ids = {
            item_id
            for item_id in self._iter_tree_items()
            if self.hierarchy_tree.item(item_id, "open")
        }
        selected = self.hierarchy_tree.selection()
        selected_id = selected[0] if selected else None

        self.hierarchy_tree.delete(*self.hierarchy_tree.get_children())
        if not self.hierarchy_rows_provider:
            return

        rows = self.hierarchy_rows_provider()
        all_enabled = all(enabled for _, _, enabled in rows) if rows else True
        self.hierarchy_tree.insert(
            "",
            tk.END,
            iid=self.HIERARCHY_ROOT_ID,
            text=self._hierarchy_root_label(all_enabled),
        )
        for node_name, parent_name, enabled in rows:
            parent_id = parent_name if parent_name else self.HIERARCHY_ROOT_ID
            label = self._hierarchy_label(node_name, enabled)
            self.hierarchy_tree.insert(parent_id, tk.END, iid=node_name, text=label)

        if not self._hierarchy_tree_initialized:
            self._expand_all_hierarchy_items()
            self._hierarchy_tree_initialized = True
        else:
            for item_id in expanded_ids:
                if self.hierarchy_tree.exists(item_id):
                    self.hierarchy_tree.item(item_id, open=True)

        if selected_id and self.hierarchy_tree.exists(selected_id):
            self.hierarchy_tree.selection_set(selected_id)

    def _iter_tree_items(self, parent: str = ""):
        """Yield all tree item ids recursively from a parent item."""
        for item_id in self.hierarchy_tree.get_children(parent):
            yield item_id
            yield from self._iter_tree_items(item_id)

    def _hierarchy_label(self, node_name: str, enabled: bool) -> str:
        """Build an ASCII checkbox-like label for hierarchy nodes."""
        marker = "[x]" if enabled else "[ ]"
        return f"{marker} {node_name}"

    def _hierarchy_root_label(self, enabled: bool) -> str:
        """Build an ASCII checkbox-like label for the synthetic root node."""
        marker = "[x]" if enabled else "[ ]"
        return f"{marker} root"

    def _expand_all_hierarchy_items(self) -> None:
        """Expand every node in the hierarchy tree."""
        for item_id in self._iter_tree_items():
            self.hierarchy_tree.item(item_id, open=True)

    def _set_all_hierarchy_enabled(self, enabled: bool) -> None:
        """Enable or disable every hierarchy subtree."""
        if not self.on_hierarchy_toggle or not self.hierarchy_rows_provider:
            return

        rows = list(self.hierarchy_rows_provider())
        if not rows:
            return

        updated_snippets = self.snippets
        for node_name, _, _ in rows:
            updated_snippets = self.on_hierarchy_toggle(node_name, enabled)

        self.snippets = updated_snippets

        active_query = self.search_var.get().strip()
        if active_query:
            self.filtered_snippets = self.fuzzy_matcher.search(active_query, self.snippets)
            self._update_snippet_list(self.filtered_snippets)
        else:
            self._update_snippet_list(self.snippets)

        self._refresh_hierarchy_tree()

    def _toggle_hierarchy_node(self, node_name: str) -> None:
        """Toggle a hierarchy subtree and refresh snippets/tree state."""
        if node_name == self.HIERARCHY_ROOT_ID:
            rows = list(self.hierarchy_rows_provider()) if self.hierarchy_rows_provider else []
            if not rows:
                return

            all_enabled = all(enabled for _, _, enabled in rows)
            self._set_all_hierarchy_enabled(not all_enabled)
            return

        if not self.on_hierarchy_toggle or not self.hierarchy_rows_provider:
            return

        rows = self.hierarchy_rows_provider()
        enabled_by_name = {name: enabled for name, _, enabled in rows}
        if node_name not in enabled_by_name:
            return

        next_enabled = not enabled_by_name[node_name]
        updated_snippets = self.on_hierarchy_toggle(node_name, next_enabled)
        self.snippets = updated_snippets

        active_query = self.search_var.get().strip()
        if active_query:
            self.filtered_snippets = self.fuzzy_matcher.search(active_query, self.snippets)
            self._update_snippet_list(self.filtered_snippets)
        else:
            self._update_snippet_list(self.snippets)

        self._refresh_hierarchy_tree()

    def _schedule_hierarchy_toggle(self, node_name: str) -> None:
        """Delay single-click toggle so double-click can cancel it."""
        self._cancel_pending_hierarchy_toggle()
        self._pending_hierarchy_item = node_name
        self._pending_hierarchy_toggle_id = self.root.after(220, self._run_pending_hierarchy_toggle)

    def _run_pending_hierarchy_toggle(self) -> None:
        """Apply a queued hierarchy toggle from a single-click gesture."""
        pending_item = self._pending_hierarchy_item
        self._pending_hierarchy_toggle_id = None
        self._pending_hierarchy_item = None
        if pending_item:
            self._toggle_hierarchy_node(pending_item)

    def _cancel_pending_hierarchy_toggle(self) -> None:
        """Cancel queued single-click toggle when double-click occurs."""
        if self._pending_hierarchy_toggle_id is not None:
            try:
                self.root.after_cancel(self._pending_hierarchy_toggle_id)
            except Exception:
                pass
        self._pending_hierarchy_toggle_id = None
        self._pending_hierarchy_item = None

    def _on_hierarchy_click(self, event: tk.Event) -> str:
        """Queue toggle on text click only; leave indicator for expand/collapse."""
        item_id = self.hierarchy_tree.identify_row(event.y)
        if not item_id:
            return "break"

        clicked_element = self.hierarchy_tree.identify("element", event.x, event.y)
        if clicked_element == "Treeitem.indicator":
            # Let Treeview handle expand/collapse without changing enable state.
            return ""

        if item_id == self.HIERARCHY_ROOT_ID:
            self.hierarchy_tree.selection_set(item_id)
            self._schedule_hierarchy_toggle(item_id)
            return "break"

        self.hierarchy_tree.selection_set(item_id)
        self._schedule_hierarchy_toggle(item_id)
        return "break"

    def _on_hierarchy_double_click(self, event: tk.Event) -> str:
        """Open mapped document on text double-click and keep indicator behavior."""
        item_id = self.hierarchy_tree.identify_row(event.y)
        if not item_id:
            return "break"

        clicked_element = self.hierarchy_tree.identify("element", event.x, event.y)
        if clicked_element == "Treeitem.indicator":
            return ""

        self._cancel_pending_hierarchy_toggle()
        self.hierarchy_tree.selection_set(item_id)
        if item_id == self.HIERARCHY_ROOT_ID:
            return ""
        if self.on_hierarchy_open:
            self.on_hierarchy_open(item_id)
        return "break"

    def _on_hierarchy_keyboard_toggle(self, event: tk.Event) -> str:
        """Toggle the currently selected hierarchy node from keyboard input."""
        _ = event
        selected = self.hierarchy_tree.selection()
        if selected:
            self._toggle_hierarchy_node(selected[0])
        return "break"

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
            self.on_close()
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
            self._refresh_hierarchy_tree()

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
        self._refresh_hierarchy_tree()
