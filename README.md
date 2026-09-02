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

The app runs in the background and listens for the global hotkey: **Ctrl+Shift+Q**

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

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for detailed development guidelines and conventions.
