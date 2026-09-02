"""Entry point for QuickType - launcher for the background app."""

import sys
from typing import List, Optional

from .app import QuickTypeApp
from .core import SnippetEngine
from .config import SnippetManager


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
        app = QuickTypeApp(hotkey="ctrl+shift+space")
        app.start()
        return 0

    elif args[0] == "add":
        # Add a snippet without launching the app
        if len(args) < 3:
            print("Usage: quicktype add <name> <content>")
            return 1
        name, content = args[1], args[2]
        manager = SnippetManager()
        engine = SnippetEngine(manager)
        engine.add_snippet(name, content)
        print(f"Added snippet: {name}")
        return 0

    elif args[0] == "remove":
        # Remove a snippet
        if len(args) < 2:
            print("Usage: quicktype remove <name>")
            return 1
        name = args[1]
        manager = SnippetManager()
        engine = SnippetEngine(manager)
        if engine.remove_snippet(name):
            print(f"Removed snippet: {name}")
            return 0
        else:
            print(f"Snippet not found: {name}")
            return 1

    elif args[0] == "list":
        # List all snippets
        manager = SnippetManager()
        snippets = manager.list_snippets()
        if not snippets:
            print("No snippets found.")
            return 0

        print("Available snippets:")
        for snippet in snippets:
            tags_str = f" [{', '.join(snippet.tags)}]" if snippet.tags else ""
            print(f"  - {snippet.name}{tags_str}")
        return 0

    else:
        print(f"Unknown command: {args[0]}")
        print("Available commands: run, add, remove, list")
        return 1


if __name__ == "__main__":
    sys.exit(main())
