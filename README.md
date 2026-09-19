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

This structure maps to sections in markdown files. Every leaf node **must** map to a Markdown document of the same name; branch nodes must not have corresponding files.

### Markdown Note Format

Each markdown file contains searchable sections with a strict format. Every section must have exactly:

# Snippet Structure Guide

Each snippet follows strict markdown formatting rules regarding cardinality and uniqueness:

* **Name/Title (`#` H1) [Exactly One]:** Acts as the primary identifier and title for the snippet. It is always visible and included in the searchable index.
* **Description (`##` H2) [At Most One]:** Provides a brief overview or summary of what the snippet does. It is visible in the UI and included in the search text.
* **Keywords (`###` H3) [At Most One]:** Stores extra search tags or alternative terms. This field is non-visible to the end user but is included for searching.
* **Explanation (`>` Blockquote) [At Most One]:** Offers detailed notes or usage context. It is visible via tooltips or secondary views but excluded from the search text.
* **Payload (Code Block) [Exactly One]:** Contains the actual executable command, code snippet, or text block. It is visible in previews and fully searchable.

## Feature Summary Table

| Component | Markdown Syntax | Cardinality | Visibility | Searchable? | Purpose | 
 | ----- | ----- | ----- | ----- | ----- | ----- | 
| **Name / Title** | `#` (H1) | **Exactly One** | Visible | Yes | Primary title and snippet identifier | 
| **Description** | `##` (H2) | **At Most One** | Visible | Yes | Brief summary or purpose of the snippet | 
| **Keywords** | `###` (H3) | **At Most One** | **Hidden** | Yes | Extra tags and alternative search terms | 
| **Explanation** | `>` (Blockquote) | **At Most One** | Visible (via tooltip) | No | Detailed notes or usage instructions | 
| **Payload** | ```` ``` ```` (Code block) | **Exactly One** | Visible (Preview) | Yes | The core command, code, or template | 


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
### port
> Opens a debugging server on the specified port
```
.server tcp:port={{port_num}}
```
````

**Searchable text includes:** H1 name + optional H2 description + optional H3 keywords + code block (blockquotes are excluded)

**Search behavior:**
- Query "bugcheck", "decode", "analyze" → ✓ Matches
- Query "displays detailed information" → ✗ No match (blockquote is ignored)
- Placeholders like `{{port num}}` are preserved for user editing

