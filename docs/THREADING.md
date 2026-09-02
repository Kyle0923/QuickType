# QuickType Threading Architecture

## Problem Fixed

**Original Issue:** Windows threading/apartment errors when running `quicktype run`
```
RuntimeError: Calling Tcl from different apartment
OSError: exception: access violation reading 0x0000000000000008
```

**Root Causes:**
1. Tkinter's `mainloop()` cannot run in a non-main thread on Windows (multi-apartment model)
2. `keyboard.listen()` is blocking and conflicted with GUI thread
3. Running GUI in a separate thread caused Tcl apartment violations

## Solution: Single Mainloop Architecture

**KEY PRINCIPLE:** Start the Tkinter mainloop **ONCE** in the main thread at app startup. Never call mainloop again. Use `withdraw()`/`deiconify()` to show/hide windows without recreating the mainloop.

### Design

```
Main Thread (app.py)
├── create GUI window once at startup (hidden with withdraw())
├── register hotkey with keyboard.add_hotkey() [non-blocking]
├── call gui_window.start_mainloop() [starts Tkinter event loop]
│   └── mainloop runs continuously, handling all events
│       ├── hotkey events trigger _on_hotkey_pressed()
│       └── GUI events (clicks, typing) handled normally
└── when mainloop exits, app exits gracefully

Hotkey Event (from keyboard library)
└── fires app._on_hotkey_pressed() [called from event loop context]
    ├── update snippet list
    └── gui_window.show() → root.deiconify() [show hidden window, NO new mainloop]

GUI Window (Tkinter)
├── created once at startup
├── hidden initially with root.withdraw()
├── shown on hotkey with root.deiconify() (in existing mainloop) ✓
└── on window close: root.withdraw() [hides, stays in mainloop]
```

### Why This Works

❌ **WRONG:** Create window → call mainloop() → hide window on close → try to call mainloop() again  
→ Error: "main thread is not in main loop"

✅ **RIGHT:** Create window → call mainloop() once → use deiconify/withdraw to show/hide → mainloop handles everything

The Tkinter mainloop is designed to run **once per application lifetime**. All window state changes (show/hide) must happen within that single running mainloop.

### Benefits

✅ **No "main thread is not in main loop" errors** – mainloop runs once, stays running  
✅ **No Tcl apartment errors** – everything in main thread  
✅ **No window recreation overhead** – same window reused  
✅ **No threading conflicts** – single mainloop handles all events  
✅ **Minimize-to-tray behavior** – natural app UX  
✅ **Clean shutdown** – proper mainloop exit on Ctrl+C  
✅ **Works on Windows/macOS/Linux** – cross-platform safe  

### Key Components

**`app.py:start()`**
- Registers hotkey (non-blocking with `keyboard.add_hotkey()`)
- **Calls `gui_window.start_mainloop()`** – This starts Tkinter event loop and blocks
- Mainloop handles all events until app exit

**`app.py:_on_hotkey_pressed()`**
- Runs within mainloop context (safe to manipulate GUI)
- Updates snippets
- Calls `gui_window.show()` which uses `deiconify()` (no new mainloop call!)

**`gui.py:SnippetSearchWindow`**
- `show()` – Updates GUI and calls `root.deiconify()` to show window (within existing mainloop)
- `start_mainloop()` – Starts the Tkinter event loop **once** and blocks
- On window close: `_hide_window()` → `root.withdraw()` (hides, keeps mainloop running)
- `destroy()` – Only called on app exit to clean up

### When Hotkey Fires

```
1. Keyboard library detects Ctrl+Shift+Q press
2. Calls app._on_hotkey_pressed() [within mainloop, safe]
3. Updates snippets and shows hidden window with deiconify()
4. User interacts with window within same mainloop
5. User clicks 'x' → window hides with withdraw() [no destroy]
6. Mainloop continues running, ready for next hotkey
7. Press hotkey again → same window shows again ✓
```

## Window Lifecycle

```
Startup:
  app.start()
  ├── hotkey_manager.register(_on_hotkey_pressed) [non-blocking]
  ├── gui_window.start_mainloop() [STARTS MAINLOOP HERE, BLOCKS]
  │   ├── mainloop runs continuously in main thread
  │   └── handles all events and GUI interactions
  └── [program exits when mainloop ends]

On Hotkey (Ctrl+Shift+Q):
  _on_hotkey_pressed() [called within mainloop context]
  ├── update_snippets()
  └── gui_window.show()
      ├── clear search input
      ├── update snippet list
      ├── deiconify() [shows hidden window, remains in mainloop]
      ├── lift() [bring to front]
      └── focus() [focus input]

User Interaction:
  ├── Type to search (handled by mainloop)
  ├── Select snippet
  ├── Press Enter or click Insert
  │   └── _on_snippet_selected()
  │       ├── insert_snippet()
  │       └── _hide_window() → withdraw() [hides window, mainloop continues]
  └── OR click Close/X
      └── _hide_window() → withdraw() [hides window, mainloop continues]

Next Hotkey:
  _on_hotkey_pressed()
  └── gui_window.show() [same hidden window shows again, still in mainloop] ✓

On App Exit (Ctrl+C):
  KeyboardInterrupt caught
  └── app.stop()
      └── gui_window.destroy() [cleanup and exit mainloop]
```

## Important Notes for Future Development

- **No GUI threading** - Always create/run Tkinter windows in main thread
- **Hotkey is non-blocking** - Callback returns quickly, doesn't block
- **No keyboard.listen()** - Use only `keyboard.add_hotkey()` approach
- **Safe for all platforms** - This pattern works on Windows/macOS/Linux
- **Text insertion** - `TextInserter.insert()` uses `keyboard.write()` which can run from any thread (safe)
