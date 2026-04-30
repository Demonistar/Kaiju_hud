# storage/database.py

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DB_PATH = os.path.join("storage", "kaiju_hud.db")

_ALLOWED_PROJECT_UPDATE_COLUMNS = {
    "name", "description", "language", "status", "designated_coder", "updated_at"
}
_ALLOWED_PROJECT_STATUSES = {"ACTIVE", "COMPLETE", "ARCHIVED"}
_ALLOWED_CODERS = {"claude", "chatgpt", "grok", "copilot"}


class Database:
    """
    Phase 1 SQLite stub.
    Creates all tables but does not perform real inserts yet.
    Dispatcher calls log_outbound() and log_inbound(), which are no-ops.
    """

    def __init__(self):
        os.makedirs("storage", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    # ---------------------------------------------------------
    # TABLE CREATION
    # ---------------------------------------------------------

    def _create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT,
            keywords TEXT,
            lead_ai TEXT,
            builder_ai TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            ai_name TEXT,
            session_name TEXT,
            status TEXT,
            created_at TEXT,
            closed_at TEXT,
            file_count INTEGER,
            token_estimate INTEGER,
            last_response TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TEXT,
            response_time_ms INTEGER,
            keyword_detected TEXT,
            routed_to TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS relay_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            state TEXT,
            from_ai TEXT,
            to_ai TEXT,
            keyword TEXT,
            content_preview TEXT,
            timestamp TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_status (
            ai_name TEXT PRIMARY KEY,
            state TEXT,
            locked_reason TEXT,
            timeout_threshold_ms INTEGER,
            avg_response_ms INTEGER,
            last_response_time_ms INTEGER,
            session_count INTEGER,
            updated_at TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            project_id INTEGER,
            summary TEXT,
            source_session_ids TEXT,
            compiled_at TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            filename TEXT,
            file_type TEXT,
            file_path TEXT,
            sent_to_ai TEXT,
            timestamp TEXT
        );
        """)

        self.conn.commit()

    # ---------------------------------------------------------
    # PHASE 1 STUB METHODS
    # ---------------------------------------------------------

    def log_outbound(self, ai_name, content, role, message_id, timestamp_ms):
        return

    def log_inbound(self, ai_name, content, message_id, timestamp_ms, response_time_ms):
        return

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


# =============================================================================
# KAIJU DATABASE — Phase 2 full-session logging and project management
# Note: PK column in projects table is 'id'; exposed as 'project_id' in API
#       because CREATE TABLE IF NOT EXISTS preserves the existing 'id' column
#       from the Database class above. _migrate_projects_table() adds the
#       Stage 1 columns (language, designated_coder, folder_path).
# =============================================================================

class KaijuDatabase:
    _ALLOWED_COLUMNS = {
        "claude_response",
        "claude_tokens",
        "claude_cost_usd",
        "chatgpt_response",
        "chatgpt_tokens",
        "chatgpt_cost_usd",
        "grok_response",
        "grok_tokens",
        "grok_cost_usd",
        "copilot_response",
        "bobby_response",
        "bobby_lesson",
    }

    def __init__(self):
        os.makedirs("storage", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_full_sessions_table()
        self._create_projects_table()
        self._migrate_full_sessions()
        self._migrate_projects_table()

    # ---------------------------------------------------------
    # TABLE CREATION
    # ---------------------------------------------------------

    def _create_full_sessions_table(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS full_sessions (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT,
                timestamp_est TEXT,
                session_id TEXT,
                active_columns TEXT,
                topic TEXT,
                keywords TEXT,
                emotion_tone TEXT,
                linked_synopsis_id INTEGER,
                linked_summary_id INTEGER,
                tags TEXT,
                user_prompt TEXT,
                claude_response TEXT,
                claude_tokens INTEGER,
                claude_cost_usd REAL,
                chatgpt_response TEXT,
                chatgpt_tokens INTEGER,
                chatgpt_cost_usd REAL,
                grok_response TEXT,
                grok_tokens INTEGER,
                grok_cost_usd REAL,
                copilot_response TEXT,
                bobby_response TEXT,
                bobby_lesson TEXT
            )
            """
        )
        self.conn.commit()

    def _create_projects_table(self):
        """
        Stage 1: projects table for Phase 2 project management.
        CREATE TABLE IF NOT EXISTS preserves the existing schema if the table
        was already created by the Database class (which uses 'id' as PK).
        _migrate_projects_table() adds the new Stage 1 columns.
        """
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                language TEXT,
                status TEXT DEFAULT 'ACTIVE',
                designated_coder TEXT DEFAULT 'claude',
                created_at TEXT,
                updated_at TEXT,
                folder_path TEXT
            )
        """)
        self.conn.commit()

    # ---------------------------------------------------------
    # MIGRATIONS (Stage 1)
    # ---------------------------------------------------------

    def _migrate_full_sessions(self):
        """
        Add Stage 2 columns to full_sessions.
        Uses try/except per column so one failure never blocks the rest.
        Logs failures to stderr; never raises.
        """
        additions = [
            ("status",           "TEXT DEFAULT 'IN_PROGRESS'"),
            ("round_mode",       "TEXT DEFAULT 'parallel'"),
            ("project_id",       "INTEGER"),
            ("completion_notes", "TEXT"),
        ]
        cur = self.conn.cursor()
        for col, typedef in additions:
            try:
                cur.execute(
                    f"ALTER TABLE full_sessions ADD COLUMN {col} {typedef}"
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists — expected on subsequent runs
            except Exception as e:
                print(
                    f"[KaijuDatabase] _migrate_full_sessions: column '{col}': {e}",
                    file=sys.stderr
                )

    def _migrate_projects_table(self):
        """
        Add Stage 1 columns to projects table.
        Uses try/except per column so one failure never blocks the rest.
        Logs failures to stderr; never raises.
        """
        additions = [
            ("language",          "TEXT"),
            ("designated_coder",  "TEXT DEFAULT 'claude'"),
            ("folder_path",       "TEXT"),
        ]
        cur = self.conn.cursor()
        for col, typedef in additions:
            try:
                cur.execute(
                    f"ALTER TABLE projects ADD COLUMN {col} {typedef}"
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
            except Exception as e:
                print(
                    f"[KaijuDatabase] _migrate_projects_table: column '{col}': {e}",
                    file=sys.stderr
                )

    # ---------------------------------------------------------
    # FULL SESSION METHODS (existing — from Phase 1 main branch)
    # ---------------------------------------------------------

    def open_round(self, session_id, user_prompt, active_columns):
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc.astimezone(ZoneInfo("America/New_York"))
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO full_sessions (
                timestamp_utc,
                timestamp_est,
                session_id,
                active_columns,
                user_prompt
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_utc.isoformat(),
                now_est.isoformat(),
                session_id,
                json.dumps(list(active_columns)),
                user_prompt,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_response(self, key_id, column_name, value):
        self._validate_column(column_name)
        cur = self.conn.cursor()
        cur.execute(
            f"UPDATE full_sessions SET {column_name} = ? WHERE key_id = ?",
            (value, key_id),
        )
        self.conn.commit()

    def get_recent_lessons(self, topic, keywords, limit=20):
        topic = topic or ""
        keywords = keywords or ""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM full_sessions
            WHERE (topic LIKE ? OR keywords LIKE ?)
            ORDER BY key_id DESC
            LIMIT ?
            """,
            (f"%{topic}%", f"%{keywords}%", int(limit)),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_row(self, key_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM full_sessions WHERE key_id = ?", (key_id,))
        row = cur.fetchone()
        return dict(row) if row else {}

    def update_late_response(self, key_id, column_name, value):
        self._validate_column(column_name)
        row = self.get_row(key_id)
        self.update_response(key_id, column_name, value)
        if row and self._is_complete_row(row):
            tags_data = {}
            if row.get("tags"):
                try:
                    tags_data = json.loads(row["tags"])
                except Exception:
                    tags_data = {}
            late_flags = tags_data.get("late_flags", [])
            if column_name not in late_flags:
                late_flags.append(column_name)
            tags_data["late_flags"] = late_flags
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE full_sessions SET tags = ? WHERE key_id = ?",
                (json.dumps(tags_data), key_id),
            )
            self.conn.commit()

    def get_max_key_id(self):
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(key_id) AS max_key_id FROM full_sessions")
        row = cur.fetchone()
        if not row:
            return 0
        max_key_id = row["max_key_id"]
        return int(max_key_id) if max_key_id is not None else 0

    # ---------------------------------------------------------
    # PROJECT METHODS (Stage 1)
    # ---------------------------------------------------------

    def create_project(self, name, description=None, language=None) -> int:
        """Create a new project record. Returns project id (rowid)."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO projects
                (name, description, language, status, designated_coder,
                 folder_path, created_at, updated_at)
            VALUES (?, ?, ?, 'ACTIVE', 'claude', ?, ?, ?)
            """,
            (name, description, language, f"Projects/{name}", now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_project(self, project_id) -> dict:
        """Get project by id. Returns dict or {}."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return dict(row) if row else {}

    def get_active_projects(self) -> list:
        """Get all projects with status ACTIVE. Returns list of dicts."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM projects WHERE status = 'ACTIVE'")
        return [dict(r) for r in cur.fetchall()]

    def update_project(self, project_id, **kwargs):
        """Update project fields. Only allows known columns."""
        filtered = {
            k: v for k, v in kwargs.items()
            if k in _ALLOWED_PROJECT_UPDATE_COLUMNS
        }
        if not filtered:
            return
        filtered["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [project_id]
        cur = self.conn.cursor()
        cur.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

    def get_project_by_name(self, name) -> dict:
        """Case-insensitive name lookup. Returns dict or {}."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM projects WHERE LOWER(name) = LOWER(?)", (name,)
        )
        row = cur.fetchone()
        return dict(row) if row else {}

    def set_project_status(self, project_id, status):
        """Set project status. Validates against allowed values."""
        if status not in _ALLOWED_PROJECT_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Allowed: {_ALLOWED_PROJECT_STATUSES}"
            )
        self.update_project(project_id, status=status)

    def set_designated_coder(self, project_id, coder_name):
        """Set designated coder. Validates against allowed values."""
        if coder_name not in _ALLOWED_CODERS:
            raise ValueError(
                f"Invalid coder '{coder_name}'. Allowed: {_ALLOWED_CODERS}"
            )
        self.update_project(project_id, designated_coder=coder_name)

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    def _validate_column(self, column_name):
        if column_name not in self._ALLOWED_COLUMNS:
            raise ValueError(f"Invalid column name: {column_name}")

    def _is_complete_row(self, row):
        response_columns = [
            "claude_response",
            "chatgpt_response",
            "grok_response",
            "copilot_response",
            "bobby_response",
        ]
        return all(row.get(col) is not None for col in response_columns)

    def _get_open_rows(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM full_sessions
            WHERE timestamp_utc IS NOT NULL
              AND datetime(timestamp_utc) <= datetime('now', '-30 seconds')
              AND (
                claude_response IS NULL
                OR chatgpt_response IS NULL
                OR grok_response IS NULL
                OR copilot_response IS NULL
                OR bobby_response IS NULL
              )
            """
        )
        return [dict(r) for r in cur.fetchall()]


# =============================================================================
# FORBIDDEN RULESET DB — Separate file, optional, never raises on missing
# =============================================================================

class ForbiddenRulesetDB:
    """
    Separate SQLite database at storage/forbidden_ruleset.db.
    Created on first access. Missing file is NOT an error — callers that
    want to check existence first should use:
        (root / "storage" / "forbidden_ruleset.db").exists()
    """

    DB_PATH = None  # Set dynamically at init using root_path

    def __init__(self, root_path):
        """
        root_path: Path object (or str) pointing to kaiju_hud root.
        DB file: root_path / storage / forbidden_ruleset.db
        Creates the DB and schema if it does not exist.
        """
        db_file = Path(root_path) / "storage" / "forbidden_ruleset.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        ForbiddenRulesetDB.DB_PATH = str(db_file)
        self.conn = sqlite3.connect(str(db_file))
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                rule_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                language  TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                added_at  TEXT,
                added_by  TEXT,
                active    INTEGER DEFAULT 1
            )
        """)
        self.conn.commit()

    def get_rules_for_language(self, language) -> list:
        """Return list of rule_text strings for given language where active=1."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT rule_text FROM rules WHERE LOWER(language) = LOWER(?) AND active = 1",
            (language,),
        )
        return [row[0] for row in cur.fetchall()]

    def add_rule(self, language, rule_text, added_by="user"):
        """Insert a new rule."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO rules (language, rule_text, added_at, added_by) VALUES (?, ?, ?, ?)",
            (language, rule_text, now, added_by),
        )
        self.conn.commit()

    def get_all_languages(self) -> list:
        """Return distinct language values where at least one active rule exists."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT DISTINCT language FROM rules WHERE active = 1"
        )
        return [row[0] for row in cur.fetchall()]
