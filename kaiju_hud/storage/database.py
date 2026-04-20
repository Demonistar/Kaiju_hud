# storage/database.py

import os
import sqlite3
from datetime import datetime


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
