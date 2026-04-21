# core/dispatcher.py

from PyQt6.QtCore import QObject, pyqtSignal, QDateTime, QTimer
from typing import List, Dict, Callable
from core.column_manager import ColumnManager


class Dispatcher(QObject):
    # AI → UI signals
    response_signal = pyqtSignal(str, str)       # (ai_name, content)
    user_message_signal = pyqtSignal(str, str)   # (ai_name, content)
    chunk_signal = pyqtSignal(str, str)          # (ai_name, chunk_text)

    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)

        # Provider registry: ai_name -> handler(content, role)
        self.providers: Dict[str, Callable[[str, str], None]] = {}

        # Optional DB client (stubbed in Phase 1)
        self.db = db_client

        # Track in‑flight messages for response time
        self._pending: Dict[str, int] = {}

    # ---------- PUBLIC API ----------

    def register_provider(self, ai_name: str, handler: Callable[[str, str], None]):
        """Register a provider handler."""
        self.providers[ai_name] = handler

    def send_message(self, targets: List[str], content: str, role: str = "user"):
        """
        Core entry point for sending messages to providers.
        Implements:
          - user_message_signal
          - sequential dispatch (1.5s)
          - collapsed column auto-exclusion
        """
        if not targets:
            return

        # Expand 'all'
        if "all" in targets:
            targets = list(self.providers.keys())

        # Fixed dispatch order
        dispatch_order = ["claude", "chatgpt", "grok", "copilot", "local"]

        delay_ms = 0
        step_ms = 1500

        for ai_name in dispatch_order:
            if ai_name not in targets:
                continue
            if ai_name not in self.providers:
                continue

            # Skip collapsed columns
            if not ColumnManager.instance().is_active(ai_name):
                continue

            message_id = self._make_message_id(ai_name)
            now_ms = self._now_ms()
            self._pending[message_id] = now_ms

            # DB outbound log (stub)
            self._log_outbound(ai_name, content, role, message_id, now_ms)

            # Emit user message immediately
            self.user_message_signal.emit(ai_name, content)

            handler = self.providers[ai_name]

            # Correct lambda capture
            def _invoke_provider(name=ai_name, msg=content, r=role, mid=message_id):
                handler_ref = self.providers.get(name)
                if handler_ref:
                    handler_ref(msg, r)

            QTimer.singleShot(delay_ms, _invoke_provider)
            delay_ms += step_ms

    # ---------- PROVIDER CALLBACKS ----------

    def on_provider_chunk(self, ai_name: str, chunk: str):
        """Providers call this for each streaming chunk."""
        self.chunk_signal.emit(ai_name, chunk)

    def on_provider_response(self, ai_name: str, content: str, message_id: str):
        """Providers call this when a full response is ready."""
        now_ms = self._now_ms()
        start_ms = self._pending.pop(message_id, now_ms)
        response_time_ms = max(0, now_ms - start_ms)

        # DB inbound log (stub)
        self._log_inbound(ai_name, content, message_id, now_ms, response_time_ms)

        # Hook for future analytics
        self.on_response_received(ai_name, content, response_time_ms)

        # Emit final response
        self.response_signal.emit(ai_name, content)

    # ---------- HOOK FOR FUTURE ANALYTICS ----------

    def on_response_received(self, ai_name: str, content: str, response_time_ms: int):
        """Phase 1: no-op."""
        pass

    # ---------- INTERNAL HELPERS ----------

    def _now_ms(self) -> int:
        return int(QDateTime.currentDateTimeUtc().toMSecsSinceEpoch())

    def _make_message_id(self, ai_name: str) -> str:
        return f"{ai_name}-{self._now_ms()}"

    def _log_outbound(self, ai_name: str, content: str, role: str,
                      message_id: str, timestamp_ms: int):
        if not self.db:
            return
        try:
            self.db.log_outbound(ai_name, content, role, message_id, timestamp_ms)
        except Exception:
            pass

    def _log_inbound(self, ai_name: str, content: str,
                     message_id: str, timestamp_ms: int, response_time_ms: int):
        if not self.db:
            return
        try:
            self.db.log_inbound(ai_name, content, message_id, timestamp_ms, response_time_ms)
        except Exception:
            pass
