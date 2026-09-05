# QuickType

A lightweight background desktop app with global hotkey trigger for quickly inserting predefined text snippets into any active window. Fuzzy search helps you find snippets instantly.

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (comes with Python)
- **Administrator privileges may be required** for global hotkey support on Windows

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/quicktype.git
   cd quicktype
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   
   On Windows:
   ```bash
   venv\Scripts\activate
   ```
   
   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```
   
   Or for core dependencies only:
   ```bash
   pip install -r requirements.txt
   ```

### Running QuickType

#### Start the background app
```bash
quicktype run
```

The app runs in the background and listens for the global hotkey: **Ctrl+Shift+Space**

Press the hotkey to open the snippet search window. Type to search, select a snippet, and press Enter to insert it into the active window.

#### Manage snippets from command line
```bash
# Add a snippet
quicktype add greet "Hello, World!"

# List all snippets
quicktype list

# Remove a snippet
quicktype remove greet
```

### Development

```bash
# Run tests with coverage
pytest

# Format code with black
black .

# Lint with ruff
ruff check .

# Type check with mypy
mypy quicktype
```

### Project Structure

- **`quicktype/app.py`** – Main application class (hotkey management + GUI)
- **`quicktype/core.py`** – Snippet engine and text insertion
- **`quicktype/config.py`** – Snippet storage and management
- **`quicktype/gui.py`** – Tkinter UI for snippet search
- **`quicktype/hotkey.py`** – Global hotkey registration
- **`quicktype/utils.py`** – Platform utilities
- **`quicktype/cli.py`** – Command-line entry point
- **`quicktype/snippet.py`** – Markdown note parser, snippet model, and storage

## Data Organization

QuickType uses a hierarchical markdown-based data structure stored in the `.data/` directory:

### Directory Structure

```
.data/
├── root.yaml           # Entry point: defines hierarchical organization
├── windbg.md           # Example: WinDbg commands and debugging tips
├── url.md              # Example: URL references
└── note_*.md           # Additional markdown files for different categories
```

### root.yaml Format

The `root.yaml` file defines how markdown files are organized into a searchable tree hierarchy. Leaf nodes map directly to section headers in markdown files.

**Example:**
```yaml
root:
  - windbg
  - shell:
    - pwsh
    - bash:
      - git
      - generic
```

This structure maps to sections in markdown files. Every leaf node **must** map to a Markdown document of the same name. Every map node **may** optionally map to a Markdown document.

### Markdown Note Format

Each markdown file contains searchable sections with a strict format. Every section must have exactly:

1. **One L1 header** (`#`) – Short name/title
2. **At most one L2 header** (`##`) – Brief description
3. **At most one blockquote block** (lines starting with `>`) – Comment, ignored in search, show up in tooltip
4. **One code block** (triple backticks) – Actual command or content

**Example (`windbg.md`):**
````markdown
# bugcheck
## decode bugcheck ID
> Analyzes a bugcheck code and displays detailed information
```
!analyze -v
!gs
```

# start TCP server
## open a debug server
> Opens a debugging server on the specified port
```
.server tcp:port={{port num}}
```
````

**Searchable text includes:** L1 header + L2 header + code block (blockquotes are excluded)

**Search behavior:**
- Query "bugcheck", "decode", "analyze" → ✓ Matches
- Query "displays detailed information" → ✗ No match (blockquote is ignored)
- Placeholders like `{{port num}}` are preserved for user editing

