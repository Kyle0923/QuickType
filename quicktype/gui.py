"""GUI components for QuickType - search window and snippet display."""

import re
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Tuple

from .snippet import Snippet
from .config import DEFAULT_HOTKEY, DEFAULT_WINDOW_GEOMETRY, DEFAULT_WINDOW_MIN_SIZE
from .core import FuzzyMatcher
from .icons import create_app_icon_image


class SnippetSearchWindow:
    """Main GUI window for searching and selecting snippets."""

    LIST_ITEM_LEFT_PAD = "  "
    HIERARCHY_ROOT_ID = "__navigation_root__"
    HIERARCHY_ROOT_LABEL = "root"
    PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)(?:\s*:\s*([^}]*?))?\s*\}\}")
    TOOLTIP_X_OFFSET = 14
    TOOLTIP_Y_OFFSET = 22
    CONTROL_MODIFIER_MASK = 0x0004

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
        on_reload: Optional[Callable[[], List[Snippet]]] = None,
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
        self.on_reload = on_reload
        self.fuzzy_matcher = FuzzyMatcher(threshold=60)
        self._final_original_text = ""
        self._placeholder_names: List[str] = []
        self._placeholder_defaults: Dict[str, str] = {}
        self._placeholder_set = set()
        self._variable_values: Dict[str, str] = {}
        self._variable_vars: Dict[str, tk.StringVar] = {}
        self._pending_hierarchy_toggle_id = None
        self._pending_hierarchy_item: Optional[str] = None
        self._hierarchy_tree_initialized = False
        self._note_tooltip: Optional[tk.Toplevel] = None
        self._note_tooltip_label: Optional[ttk.Label] = None
        self._tooltip_index: Optional[int] = None

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

        hierarchy_header = ttk.Frame(hierarchy_frame)
        hierarchy_header.pack(fill=tk.X)

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
        self.hierarchy_tree.bind("<Button-3>", self._on_hierarchy_right_click)
        self.hierarchy_tree.bind("<space>", self._on_hierarchy_keyboard_toggle)
        self.hierarchy_tree.bind("<Return>", self._on_hierarchy_keyboard_toggle)

        variables_frame = ttk.LabelFrame(sidebar_split, text="Variables")
        variables_frame.rowconfigure(1, weight=1)
        variables_frame.columnconfigure(0, weight=1)

        variables_header = ttk.Frame(variables_frame)
        variables_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._create_action_button(
            variables_header, text="Clear", command=self._clear_variables
        ).pack(side=tk.LEFT, padx=(6, 0), pady=(0, 2))

        self.variable_canvas = tk.Canvas(variables_frame, borderwidth=0, highlightthickness=0)
        self.variable_canvas.grid(row=1, column=0, sticky="nsew")

        variable_scrollbar = ttk.Scrollbar(
            variables_frame,
            orient=tk.VERTICAL,
            command=self.variable_canvas.yview,
        )
        variable_scrollbar.grid(row=1, column=1, sticky="ns")
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
        self.snippet_listbox.bind("<Motion>", self._on_list_hover)
        self.snippet_listbox.bind("<Leave>", self._on_list_leave)
        self.snippet_listbox.bind("<Double-1>", self._on_snippet_double_click)
        self.snippet_listbox.bind("<Button-3>", self._on_snippet_right_click)
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

        self._create_action_button(
            final_header, text="Reset", command=self._reset_final_text
        ).pack(side=tk.LEFT, padx=(6, 0), pady=(0, 2))

        self._create_action_button(
            final_header, text="Enter", command=self._insert_selected
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

    @staticmethod
    def _create_action_button(parent: tk.Misc, text: str, command: Callable[[], None]) -> tk.Button:
        """Create a compact pane action button with the shared Final-pane styling."""
        return tk.Button(
            parent,
            text=text,
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
            command=command,
        )

    def _setup_menu(self) -> None:
        """Create the top-level menu bar with application settings."""
        menubar = tk.Menu(self.root)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Hotkey...", command=self._open_hotkey_dialog)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        menubar.add_command(label="Reload", command=self._reload_data)
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
        _ = event
        selection = self.snippet_listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            if self.selected_index < len(self.filtered_snippets):
                self._update_preview(self.filtered_snippets[self.selected_index])

    def _on_list_hover(self, event: tk.Event) -> str:
        """Show a tooltip with markdown note text when hovering a snippet row."""
        index = self.snippet_listbox.nearest(event.y)
        tooltip_text = self._get_snippet_tooltip_text(index)

        if not tooltip_text:
            self._hide_note_tooltip()
            return "break"

        screen_x = event.x_root + self.TOOLTIP_X_OFFSET
        screen_y = event.y_root + self.TOOLTIP_Y_OFFSET
        self._show_note_tooltip(tooltip_text, screen_x, screen_y, index)
        return "break"

    def _on_list_leave(self, event: tk.Event) -> str:
        """Hide note tooltip when pointer leaves the snippet list."""
        _ = event
        self._hide_note_tooltip()
        return "break"

    def _get_snippet_tooltip_text(self, index: int) -> Optional[str]:
        """Return tooltip text for a list index, using snippet note/quote text."""
        if index < 0 or index >= len(self.filtered_snippets):
            return None

        note_text = (self.filtered_snippets[index].note or "").strip()
        return note_text or None

    def _show_note_tooltip(self, text: str, x: int, y: int, index: int) -> None:
        """Create or update lightweight tooltip near the hovered list row."""
        if self._note_tooltip is None:
            self._note_tooltip = tk.Toplevel(self.root)
            self._note_tooltip.wm_overrideredirect(True)
            self._note_tooltip.attributes("-topmost", True)
            self._note_tooltip_label = ttk.Label(
                self._note_tooltip,
                text=text,
                justify=tk.LEFT,
                wraplength=360,
                padding=(8, 6),
                relief=tk.SOLID,
                borderwidth=1,
            )
            self._note_tooltip_label.pack()
        elif self._note_tooltip_label:
            self._note_tooltip_label.config(text=text)

        self._tooltip_index = index
        self._note_tooltip.deiconify()
        self._note_tooltip.update_idletasks()

        tooltip_width = self._note_tooltip.winfo_reqwidth()
        tooltip_height = self._note_tooltip.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        bounded_x = max(0, min(x, max(screen_width - tooltip_width - 4, 0)))
        bounded_y = max(0, min(y, max(screen_height - tooltip_height - 4, 0)))
        self._note_tooltip.geometry(f"+{bounded_x}+{bounded_y}")

    def _hide_note_tooltip(self) -> None:
        """Hide tooltip if currently visible."""
        self._tooltip_index = None
        if self._note_tooltip is not None:
            self._note_tooltip.withdraw()

    def _open_snippet_location(self, snippet: Snippet) -> None:
        """Open a snippet's source location in VS Code."""
        if not snippet.location:
            return

        try:
            subprocess.Popen(
                ["code", "-r", "-g", snippet.location],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"Error opening snippet location: {e}")

    def _on_snippet_double_click(self, event: tk.Event) -> str:
        """Insert the selected snippet, use keyboard mode if Ctrl is held."""
        if not self._select_snippet_at_event(event):
            return "break"

        mode = "type" if event.state & self.CONTROL_MODIFIER_MASK else "paste"
        self._insert_selected(mode=mode)
        return "break"

    def _on_snippet_right_click(self, event: tk.Event) -> str:
        """Open the selected snippet's source location in VS Code on right-click."""
        if not self._select_snippet_at_event(event):
            return "break"

        self._open_snippet_location(self.filtered_snippets[self.selected_index])
        return "break"

    def _select_snippet_at_event(self, event: tk.Event) -> bool:
        """Select and preview the snippet located at a pointer event."""
        index = self.snippet_listbox.nearest(event.y)
        if index < 0 or index >= len(self.filtered_snippets):
            return False

        self.selected_index = index
        self.snippet_listbox.selection_clear(0, tk.END)
        self.snippet_listbox.selection_set(index)
        self.snippet_listbox.activate(index)
        self._update_preview(self.filtered_snippets[index])
        return True

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
        normalized_preview = self._normalize_placeholders(snippet.payload)
        placeholders, defaults = self._extract_placeholders(snippet.payload)

        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, normalized_preview)
        self.preview_text.config(state=tk.DISABLED)

        self._final_original_text = normalized_preview
        self._placeholder_names = placeholders
        self._placeholder_set = set(placeholders)
        self._placeholder_defaults = defaults
        self._render_variable_editor(placeholders)
        self._refresh_final_text_from_variables()

    def _reset_final_text(self) -> None:
        """Restore the editable final text to the last selected snippet payload."""
        for name, variable_var in self._variable_vars.items():
            variable_var.set(self._placeholder_defaults.get(name, ""))
        self._refresh_final_text_from_variables()

    def _clear_variables(self) -> None:
        """Clear saved variable values and leave only current snippet placeholders."""
        self._variable_values.clear()
        self._render_variable_editor(self._placeholder_names)
        self._refresh_final_text_from_variables()

    def _reload_data(self) -> None:
        """Reload the configured data directory and refresh navigation and snippets."""
        if not self.on_reload:
            return

        self.snippets = self.on_reload()
        self._hierarchy_tree_initialized = False
        self._update_snippet_list(self.snippets)
        self._refresh_hierarchy_tree()

    def _extract_placeholders(self, text: str) -> Tuple[List[str], Dict[str, str]]:
        """Extract unique placeholder names/defaults from {{name[:default]}} tokens."""
        ordered: List[str] = []
        seen = set()
        defaults: Dict[str, str] = {}
        for match in self.PLACEHOLDER_PATTERN.finditer(text):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
            if name:
                raw_default = match.group(2)
                default_value = raw_default.strip() if raw_default is not None else ""
                if name not in defaults:
                    defaults[name] = default_value
        return ordered, defaults

    def _normalize_placeholders(self, text: str) -> str:
        """Normalize placeholders to {{name}} for preview/final template rendering."""

        def replace(match: re.Match) -> str:
            name = match.group(1).strip()
            return f"{{{{{name}}}}}"

        return self.PLACEHOLDER_PATTERN.sub(replace, text)

    def _replace_with_current_variables(self, text: str) -> str:
        """Replace placeholders with user-provided values when available."""

        def replace(match: re.Match) -> str:
            key = match.group(1).strip()
            current_value = self._get_current_variable_value(key)
            if current_value is not None:
                value = current_value
                return value if value else match.group(0)
            if key in self._placeholder_defaults:
                default_value = self._placeholder_defaults.get(key, "")
                return default_value if default_value else match.group(0)
            return match.group(0)

        return self.PLACEHOLDER_PATTERN.sub(replace, text)

    def _get_current_variable_value(self, name: str) -> Optional[str]:
        """Return the runtime value for a variable from visible input or saved user values."""
        variable_vars = getattr(self, "_variable_vars", {})
        variable_var = variable_vars.get(name)
        if variable_var is not None:
            return variable_var.get()
        variable_values = getattr(self, "_variable_values", {})
        if name in variable_values:
            return variable_values[name]
        return None

    def _get_variable_editor_names(self, placeholders: List[str]) -> List[str]:
        """Keep current placeholders first, then persist previously edited variable names."""
        names = list(placeholders)
        for name in self._variable_values.keys():
            if name not in names:
                names.append(name)
        return names

    def _render_variable_editor(self, placeholders: List[str]) -> None:
        """Render variable entry rows based on placeholders in the selected snippet."""
        self._placeholder_names = placeholders
        self._placeholder_set = set(placeholders)
        self._variable_vars = {}
        display_names = self._get_variable_editor_names(placeholders)

        for child in self.variable_container.winfo_children():
            child.destroy()

        if not display_names:
            ttk.Label(
                self.variable_container,
                text="No placeholders in this snippet.",
            ).grid(row=0, column=0, padx=6, pady=6, sticky="w")
            return

        for row_index, placeholder in enumerate(display_names):
            ttk.Label(
                self.variable_container,
                text=placeholder,
            ).grid(row=row_index, column=0, padx=(6, 4), pady=4, sticky="w")

            if placeholder in self._variable_values:
                initial_value = self._variable_values[placeholder]
            else:
                initial_value = self._placeholder_defaults.get(placeholder, "")

            value_var = tk.StringVar(value=initial_value)
            value_var.trace_add(
                "write",
                lambda *args, variable_name=placeholder: self._on_variable_change(variable_name),
            )
            entry = ttk.Entry(self.variable_container, textvariable=value_var, width=18)
            entry.grid(row=row_index, column=1, padx=(0, 6), pady=4, sticky="ew")
            self._variable_vars[placeholder] = value_var

        self.variable_container.columnconfigure(1, weight=1)

    def _on_variable_change(self, variable_name: str) -> None:
        """Track variable values and refresh final text after edits."""
        variable_var = self._variable_vars.get(variable_name)
        if variable_var is not None:
            self._variable_values[variable_name] = variable_var.get()
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
        states = self._hierarchy_states(rows)
        self.hierarchy_tree.insert(
            "",
            tk.END,
            iid=self.HIERARCHY_ROOT_ID,
            text=self._hierarchy_label(self.HIERARCHY_ROOT_LABEL, states[self.HIERARCHY_ROOT_ID]),
        )
        for node_name, parent_name, _ in rows:
            parent_id = parent_name if parent_name else self.HIERARCHY_ROOT_ID
            label = self._hierarchy_label(node_name, states[node_name])
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

    def _hierarchy_label(self, node_name: str, state: str) -> str:
        """Build an ASCII checkbox-like label for hierarchy nodes."""
        labels = {
            "UNCHECKED": "☐",
            "CHECKED": "☑",
            "PARTIAL": "☒",
        }
        marker = labels.get(state, "UNCHECKED")
        return f"{marker} {node_name}"

    def _expand_all_hierarchy_items(self) -> None:
        """Expand every node in the hierarchy tree."""
        for item_id in self._iter_tree_items():
            self.hierarchy_tree.item(item_id, open=True)

    def _hierarchy_states(self, rows: List[Tuple[str, Optional[str], bool]]) -> Dict[str, str]:
        """Return checkbox states derived from each node's complete subtree."""
        children_by_parent: Dict[str, List[str]] = {self.HIERARCHY_ROOT_ID: []}
        enabled_by_name = {name: enabled for name, _, enabled in rows}
        for node_name, parent_name, _ in rows:
            parent_id = parent_name if parent_name else self.HIERARCHY_ROOT_ID
            children_by_parent.setdefault(parent_id, []).append(node_name)

        states: Dict[str, str] = {}

        def visit(node_name: str) -> List[bool]:
            child_names = children_by_parent.get(node_name, [])
            if not child_names:
                subtree_enabled = [enabled_by_name[node_name]]
            else:
                subtree_enabled = []
            for child_name in child_names:
                subtree_enabled.extend(visit(child_name))
            if all(subtree_enabled):
                states[node_name] = "CHECKED"
            elif any(subtree_enabled):
                states[node_name] = "PARTIAL"
            else:
                states[node_name] = "UNCHECKED"
            return subtree_enabled

        visit(self.HIERARCHY_ROOT_ID)
        return states

    @staticmethod
    def _hierarchy_relations(
        rows: List[Tuple[str, Optional[str], bool]], root_id: str
    ) -> Tuple[Dict[str, Optional[str]], Dict[str, List[str]]]:
        """Build parent and child indexes for hierarchy rows."""
        parent_by_name = {name: parent or root_id for name, parent, _ in rows}
        children_by_parent: Dict[str, List[str]] = {root_id: []}
        for node_name, parent_name, _ in rows:
            children_by_parent.setdefault(parent_name or root_id, []).append(node_name)
        return parent_by_name, children_by_parent

    def _hierarchy_toggle_targets(
        self, rows: List[Tuple[str, Optional[str], bool]], node_name: str
    ) -> Dict[str, bool]:
        """Return effective node states after applying a checkbox click."""
        enabled_by_name = {name: enabled for name, _, enabled in rows}
        parent_by_name, children_by_parent = self._hierarchy_relations(
            rows, self.HIERARCHY_ROOT_ID
        )
        states = self._hierarchy_states(rows)
        target_enabled = states[node_name] != "CHECKED"

        def set_subtree_enabled(current_name: str) -> None:
            if current_name in enabled_by_name:
                enabled_by_name[current_name] = target_enabled
            for child_name in children_by_parent.get(current_name, []):
                set_subtree_enabled(child_name)

        set_subtree_enabled(node_name)
        if target_enabled:
            current_parent = parent_by_name.get(node_name)
            while current_parent and current_parent != self.HIERARCHY_ROOT_ID:
                enabled_by_name[current_parent] = True
                current_parent = parent_by_name.get(current_parent)
        return enabled_by_name

    def _hierarchy_focus_targets(
        self, rows: List[Tuple[str, Optional[str], bool]], node_name: str
    ) -> Dict[str, bool]:
        """Enable one node's subtree and the ancestors required to reach it."""
        parent_by_name, children_by_parent = self._hierarchy_relations(
            rows, self.HIERARCHY_ROOT_ID
        )
        enabled_by_name = {name: False for name, _, _ in rows}

        def enable_subtree(current_name: str) -> None:
            if current_name in enabled_by_name:
                enabled_by_name[current_name] = True
            for child_name in children_by_parent.get(current_name, []):
                enable_subtree(child_name)

        enable_subtree(node_name)
        current_parent = parent_by_name.get(node_name)
        while current_parent and current_parent != self.HIERARCHY_ROOT_ID:
            enabled_by_name[current_parent] = True
            current_parent = parent_by_name.get(current_parent)
        return enabled_by_name

    def _apply_hierarchy_targets(
        self, rows: List[Tuple[str, Optional[str], bool]], target_enabled: Dict[str, bool]
    ) -> None:
        """Persist effective states, including descendants hidden by disabled ancestors."""
        if not self.on_hierarchy_toggle:
            return

        parent_by_name, _ = self._hierarchy_relations(rows, self.HIERARCHY_ROOT_ID)
        updated_snippets = self.snippets
        # Clear every explicit disable first; this makes the desired effective state unambiguous.
        for node_name, _, _ in rows:
            updated_snippets = self.on_hierarchy_toggle(node_name, True)
        # Disabling only the highest inactive nodes preserves the requested active descendants.
        for node_name, enabled in target_enabled.items():
            parent_name = parent_by_name[node_name]
            is_topmost_disabled = (
                parent_name == self.HIERARCHY_ROOT_ID or target_enabled[parent_name]
            )
            if not enabled and is_topmost_disabled:
                updated_snippets = self.on_hierarchy_toggle(node_name, False)

        self.snippets = updated_snippets
        active_query = self.search_var.get().strip()
        if active_query:
            self.filtered_snippets = self.fuzzy_matcher.search(active_query, self.snippets)
            self._update_snippet_list(self.filtered_snippets)
        else:
            self._update_snippet_list(self.snippets)
        self._refresh_hierarchy_tree()

    def _set_all_hierarchy_enabled(self, enabled: bool) -> None:
        """Enable or disable every hierarchy subtree."""
        if not self.on_hierarchy_toggle or not self.hierarchy_rows_provider:
            return

        rows = list(self.hierarchy_rows_provider())
        if not rows:
            return

        self._apply_hierarchy_targets(rows, {node_name: enabled for node_name, _, _ in rows})

    def _toggle_hierarchy_node(self, node_name: str) -> None:
        """Toggle a hierarchy subtree and refresh snippets/tree state."""

        if node_name == self.HIERARCHY_ROOT_ID:
            rows = list(self.hierarchy_rows_provider()) if self.hierarchy_rows_provider else []
            if not rows:
                return

            root_state = self._hierarchy_states(rows)[self.HIERARCHY_ROOT_ID]
            self._set_all_hierarchy_enabled(root_state != "CHECKED")
            return

        if not self.on_hierarchy_toggle or not self.hierarchy_rows_provider:
            return

        rows = self.hierarchy_rows_provider()
        if node_name not in {name for name, _, _ in rows}:
            return

        self._apply_hierarchy_targets(rows, self._hierarchy_toggle_targets(rows, node_name))

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


        self.hierarchy_tree.selection_set(item_id)
        self._schedule_hierarchy_toggle(item_id)
        return "break"

    def _on_hierarchy_double_click(self, event: tk.Event) -> str:
        """Enable only the selected hierarchy subtree on double-click."""
        item_id = self.hierarchy_tree.identify_row(event.y)
        if not item_id:
            return "break"

        clicked_element = self.hierarchy_tree.identify("element", event.x, event.y)
        if clicked_element == "Treeitem.indicator":
            return ""

        self._cancel_pending_hierarchy_toggle()
        self.hierarchy_tree.selection_set(item_id)
        if not self.hierarchy_rows_provider:
            return "break"

        rows = list(self.hierarchy_rows_provider())
        if item_id == self.HIERARCHY_ROOT_ID:
            self._set_all_hierarchy_enabled(True)
        elif item_id in {name for name, _, _ in rows}:
            self._apply_hierarchy_targets(rows, self._hierarchy_focus_targets(rows, item_id))
        return "break"

    def _on_hierarchy_right_click(self, event: tk.Event) -> str:
        """Open the mapped hierarchy document on right-click."""
        item_id = self.hierarchy_tree.identify_row(event.y)
        if not item_id:
            return "break"

        clicked_element = self.hierarchy_tree.identify("element", event.x, event.y)
        if clicked_element == "Treeitem.indicator":
            return ""

        self._cancel_pending_hierarchy_toggle()
        self.hierarchy_tree.selection_set(item_id)
        if item_id == self.HIERARCHY_ROOT_ID:
            return "break"
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
            self._hide_note_tooltip()
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
            if self._note_tooltip is not None:
                self._note_tooltip.destroy()
                self._note_tooltip = None
                self._note_tooltip_label = None
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def update_snippets(self, snippets: List[Snippet]) -> None:
        """Update the list of available snippets."""
        self.snippets = snippets
        self._update_snippet_list(snippets)
        self._refresh_hierarchy_tree()
