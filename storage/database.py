# storage/database.py

import json
import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DB_PATH = os.path.join("storage", "kaiju_hud.db")


class Database:
    """
    Phase 1 SQLite stub.
    Creates all tables but does not perform real inserts yet.
    Dispatcher calls log_outbound() and log_inbound(), which are no-ops.

    Phase 2 will implement:
      - message logging
      - session tracking
      - project management
      - relay logs
      - AI performance metrics
      - knowledge topic compilation
      - file tracking
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

        # -------------------------
        # projects
        # -------------------------
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

        # -------------------------
        # sessions
        # -------------------------
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

        # -------------------------
        # messages
        # -------------------------
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

        # -------------------------
        # relay_log
        # -------------------------
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

        # -------------------------
        # ai_status
        # -------------------------
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

        # -------------------------
        # knowledge_topics
        # -------------------------
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

        # -------------------------
        # files
        # -------------------------
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
        """
        Phase 1: stub only.
        Phase 2: insert into messages table.
        """
        return

    def log_inbound(self, ai_name, content, message_id, timestamp_ms, response_time_ms):
        """
        Phase 1: stub only.
        Phase 2: insert into messages table and update ai_status.
        """
        return

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


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
