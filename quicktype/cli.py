"""Entry point for QuickType - launcher for the background app."""

import sys
from typing import List, Optional

from .app import QuickTypeApp
from .config import DEFAULT_HOTKEY
from .core import SnippetEngine
from .snippet import SnippetManager

def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for QuickType.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] == "run":
        # Launch the background app (default behavior)
        app = QuickTypeApp(hotkey=DEFAULT_HOTKEY)
        app.start()
        return 0

    elif args[0] == "add":
        # Add a snippet without launching the app
        if len(args) < 4:
            print("Usage: quicktype add <group> <name> <payload> [description]")
            return 1
        group, name, payload = args[1], args[2], args[3]
        description = args[4] if len(args) > 4 else None
        manager = SnippetManager()
        engine = SnippetEngine(manager)
        engine.add_snippet(name=name, payload=payload, group=group, description=description)
        print(f"Added snippet: {name} ({group})")
        return 0

    elif args[0] == "list":
        # List all snippets
        manager = SnippetManager()
        snippets = manager.list_snippets()
        if not snippets:
            print("No snippets found.")
            return 0

        print("Available snippets:")
        for snippet in snippets:
            print(f"  * {snippet.name}{' - ' + snippet.description if snippet.description else ''}")
        return 0

    else:
        print(f"Unknown command: {args[0]}")
        print("Available commands: run, add, list")
        return 1


if __name__ == "__main__":
    sys.exit(main())
