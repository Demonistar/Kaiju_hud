# KAIJU HUD — PHASE 2 STAGE 1 INSTRUCTION
# DB Schema + Folder Structure + FileBroker Root Fix
# Read KAIJU_PHASE2_MASTER.md first. Then execute this document top to bottom.

---

## STAGE 1 SCOPE

This stage touches exactly these things:
1. storage/database.py — add new columns and tables to kaiju_hud.db
2. core/file_broker.py — fix hardcoded root, add ensure_project_folder()
3. providers/claude_provider.py — fix hardcoded D:\AI\kaiju_hud path
4. Create Projects/ folder at repo root if it does not exist
5. Create storage/forbidden_ruleset.db schema (empty, ready for data)

This stage does NOT implement any Bobby orchestration logic.
This stage does NOT modify dispatcher.py.
This stage does NOT modify ollama_client.py.
This stage does NOT touch any UI files.
Stop at the completion checklist. Do not begin Stage 2.

---

## TASK 1 — storage/database.py

### 1A — Add columns to full_sessions table

Use ALTER TABLE to add these columns if they do not already exist.
Check existence before adding — do not error if column is present.
Add all of these to the full_sessions table:

```sql
ALTER TABLE full_sessions ADD COLUMN status TEXT DEFAULT 'IN_PROGRESS';
ALTER TABLE full_sessions ADD COLUMN round_mode TEXT DEFAULT 'parallel';
ALTER TABLE full_sessions ADD COLUMN project_id INTEGER;
ALTER TABLE full_sessions ADD COLUMN completion_notes TEXT;
```

- status values will be: 'IN_PROGRESS', 'COMPLETE', 'REVIEW'
- round_mode values will be: 'parallel', 'moa'
- project_id is a foreign key to the projects table (created below)
- completion_notes is free text, nullable

Implement this as a _migrate_full_sessions() method called from __init__
in KaijuDatabase. Use try/except per column so one failure doesn't block
the rest. Log failures to stderr only, do not raise.

### 1B — Create projects table

Add this to KaijuDatabase._create_full_sessions_table() or as its own
_create_projects_table() method called from __init__:

```sql
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    language TEXT,
    status TEXT DEFAULT 'ACTIVE',
    designated_coder TEXT DEFAULT 'claude',
    created_at TEXT,
    updated_at TEXT,
    folder_path TEXT
);
```

- name: user-provided project name, e.g. "Boogaboo"
- language: e.g. "LSL", "PyQt6", "GDScript", "Python" — used for ruleset lookup
- status: 'ACTIVE' | 'COMPLETE' | 'ARCHIVED'
- designated_coder: 'claude' | 'chatgpt' | 'grok' | 'copilot' — default claude
- folder_path: relative path from root, e.g. "Projects/Boogaboo"
- created_at / updated_at: ISO 8601 UTC strings

### 1C — Add KaijuDatabase methods for projects

Add these methods to KaijuDatabase:

```python
def create_project(self, name, description=None, language=None) -> int:
    """Create a new project record. Returns project_id."""
    # Insert into projects table
    # Set folder_path to f"Projects/{name}"
    # Set created_at and updated_at to now UTC ISO
    # Return lastrowid

def get_project(self, project_id) -> dict:
    """Get project by ID. Returns dict or {}."""

def get_active_projects(self) -> list:
    """Get all projects with status ACTIVE. Returns list of dicts."""

def update_project(self, project_id, **kwargs):
    """Update project fields. Only allows known columns."""
    # Allowed: name, description, language, status, designated_coder, updated_at

def get_project_by_name(self, name) -> dict:
    """Case-insensitive name lookup. Returns dict or {}."""

def set_project_status(self, project_id, status):
    """Set project status. Validates against allowed values."""
    # Allowed: ACTIVE, COMPLETE, ARCHIVED

def set_designated_coder(self, project_id, coder_name):
    """Set designated coder. Validates against allowed values."""
    # Allowed: claude, chatgpt, grok, copilot
```

### 1D — Create storage/forbidden_ruleset.db

Create a SEPARATE database file at storage/forbidden_ruleset.db.
This is NOT added to kaiju_hud.db.
Create a ForbiddenRulesetDB class in storage/database.py (same file,
separate class from KaijuDatabase).

```python
class ForbiddenRulesetDB:
    DB_PATH = None  # Set dynamically at init using root detection

    def __init__(self, root_path):
        """
        root_path: Path object pointing to kaiju_hud root.
        DB file: root_path / storage / forbidden_ruleset.db
        If DB does not exist, create it with schema.
        If DB exists, open it.
        """

    def _create_tables(self):
        # Create rules table:
        # CREATE TABLE IF NOT EXISTS rules (
        #     rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        #     language TEXT NOT NULL,
        #     rule_text TEXT NOT NULL,
        #     added_at TEXT,
        #     added_by TEXT,
        #     active INTEGER DEFAULT 1
        # )

    def get_rules_for_language(self, language) -> list:
        """Return list of rule_text strings for given language where active=1."""

    def add_rule(self, language, rule_text, added_by="user"):
        """Insert a new rule."""

    def get_all_languages(self) -> list:
        """Return distinct language values."""
```

Important: ForbiddenRulesetDB.__init__ must NOT raise if the file doesn't
exist — it creates it. Callers that check for the file before calling this
class should use: (root / "storage" / "forbidden_ruleset.db").exists()

---

## TASK 2 — core/file_broker.py

### 2A — Fix hardcoded ROOT

Current code:
```python
ROOT = os.path.abspath(".")
```

Replace with dynamic root detection based on main.py location.
FileBroker needs to find the repo root reliably regardless of working
directory or drive letter.

Replace the class-level ROOT with a dynamic property:

```python
from pathlib import Path

class FileBroker:
    def __init__(self):
        # Walk up from this file's location to find main.py
        # file_broker.py is at kaiju_hud/core/file_broker.py
        # So root is two levels up from this file
        self.ROOT = Path(__file__).resolve().parent.parent
```

Update all uses of self.ROOT or FileBroker.ROOT in the class to use
self.ROOT as a Path object. os.path.join calls should use Path / operator
or str(self.ROOT / relative_path).

### 2B — Add ensure_project_folder() method

```python
def ensure_project_folder(self, project_name: str) -> str:
    """
    Creates Projects/[project_name]/ under ROOT if it doesn't exist.
    Returns the relative path string: "Projects/[project_name]"
    """
    folder = self.ROOT / "Projects" / project_name
    folder.mkdir(parents=True, exist_ok=True)
    return str(Path("Projects") / project_name)
```

### 2C — Create Projects/ folder at root

In FileBroker.__init__, after setting self.ROOT:
```python
(self.ROOT / "Projects").mkdir(exist_ok=True)
```

This ensures Projects/ always exists when the HUD starts.

---

## TASK 3 — providers/claude_provider.py

### 3A — Fix hardcoded path in FILE_SYSTEM_PREFIX

Current:
```python
FILE_SYSTEM_PREFIX = """You have direct read/write access to the Kaiju HUD project at D:\\AI\\kaiju_hud via FileBroker.
...
Project root: D:\\AI\\kaiju_hud
"""
```

Replace with dynamic root resolution:

```python
from pathlib import Path

def _get_file_system_prefix() -> str:
    root = Path(__file__).resolve().parent.parent
    return f"""You have direct read/write access to the Kaiju HUD project at {root} via FileBroker.

To read a file, respond with exactly:
READ: path/to/file.py

To write a file, respond with exactly:
WRITE: path/to/file.py
<<<FILE_CONTENT>>>
(complete file contents here)
<<<END>>>

You can chain multiple READ and WRITE commands in one response.
The HUD will execute them and show you the results.
Project root: {root}
"""

FILE_SYSTEM_PREFIX = _get_file_system_prefix()
```

This generates the prefix once at import time using the actual runtime root.
No hardcoded paths remain.

---

## TASK 4 — Verify Projects/ folder exists at repo root

After completing Tasks 1-3, confirm that running main.py creates a
Projects/ folder at the repo root if one does not exist.
This is handled by FileBroker.__init__ in Task 2C.
No additional work needed beyond that.

---

## COMPLETION CHECKLIST

Before stopping, verify every item on this list. Do not mark complete
if any item is unverified.

### Database
- [ ] full_sessions table has: status, round_mode, project_id, completion_notes columns
- [ ] projects table exists with all columns defined in Task 1B
- [ ] All KaijuDatabase project methods exist and are callable
- [ ] ForbiddenRulesetDB class exists in storage/database.py
- [ ] ForbiddenRulesetDB creates storage/forbidden_ruleset.db on first run
- [ ] ForbiddenRulesetDB.get_rules_for_language() returns empty list (not error) when no rules exist
- [ ] _migrate_full_sessions() uses try/except per column, does not raise

### FileBroker
- [ ] FileBroker.ROOT is dynamic (Path(__file__) based), no hardcoded strings
- [ ] FileBroker.ensure_project_folder() exists and creates the folder
- [ ] Projects/ folder is created at root on FileBroker init
- [ ] All existing FileBroker methods (read, write, list_files) still work

### ClaudeProvider
- [ ] FILE_SYSTEM_PREFIX contains no hardcoded D:\ or C:\ paths
- [ ] FILE_SYSTEM_PREFIX correctly shows actual runtime root path
- [ ] _get_file_system_prefix() function exists and is called at module level

### General
- [ ] main.py starts without errors after these changes
- [ ] Existing Phase 1 parallel dispatch still works (send a test prompt)
- [ ] No imports broken in any modified file
- [ ] No existing tests broken (if test files exist)

---

## IF SOMETHING IS AMBIGUOUS

Stop. Add a comment in the relevant file:
# STAGE 1 FLAG: [describe the ambiguity]
Then report what you flagged before finishing.
Do not guess. Do not silently resolve conflicts.

---

## AFTER COMPLETION

Commit with message:
"Phase 2 Stage 1: DB schema, Projects folder, FileBroker root fix"

Then stop. Wait for Stage 2 instructions.
Do not begin implementing Bobby orchestration logic.
Do not modify dispatcher.py.
Do not modify ollama_client.py.

---

END OF STAGE 1
