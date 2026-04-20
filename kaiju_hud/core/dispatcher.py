# core/dispatcher.py

from PyQt6.QtCore import QObject, pyqtSignal, QDateTime, QTimer
from typing import List, Dict, Callable


# Canonical dispatch order — always respected regardless of targets list
DISPATCH_ORDER = ["claude", "chatgpt", "grok", "copilot", "local"]


class Dispatcher(QObject):
    # Emitted when a response is ready for a specific AI
    # ui panels connect to this and filter by ai_name
    response_signal = pyqtSignal(str, str)      # ai_name, content
    # Emitted when a user message is sent to a specific AI
    user_message_signal = pyqtSignal(str, str)  # ai_name, content
    # Emitted by streaming providers for each token chunk
    chunk_signal = pyqtSignal(str, str)          # ai_name, chunk_text

    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)

        # Provider registry: ai_name -> callable(prompt, role) -> str/async
        self.providers: Dict[str, Callable[[str, str], None]] = {}

        # Optional DB client (stubbed in Phase 1)
        self.db = db_client

        # Track in‑flight messages for response time
        # key: message_id -> send_timestamp_ms
        self._pending: Dict[str, int] = {}

    # ---------- PUBLIC API ----------

    def register_provider(self, ai_name: str, handler: Callable[[str, str], None]):
        """
        Register a provider handler.
        handler(content, role) must eventually call
        dispatcher.on_provider_response(ai_name, content, message_id)
        """
        self.providers[ai_name] = handler

    def send_message(self, targets: List[str], content: str, role: str = "user"):
        """
        Core entry point.
        Called by:
          - Prompt bar (UI)
          - Internal systems (Phase 2 relay, memory, etc.)
        targets: ['claude'], ['chatgpt', 'grok'], ['all'], etc.
        """
        if not targets:
            return

        # Expand 'all' into concrete targets
        if "all" in targets:
            targets = list(self.providers.keys())

        # Import here to avoid circular imports at module load time
        from core.column_manager import ColumnManager

        # Sequential dispatch in canonical order: 1.5s between each provider
        delay_ms = 0
        step_ms = 1500

        for ai_name in DISPATCH_ORDER:
            if ai_name not in targets:
                continue
            if ai_name not in self.providers:
                continue
            # Skip collapsed/hidden columns to avoid wasting API tokens
            if not ColumnManager.instance().is_active(ai_name):
                continue

            message_id = self._make_message_id(ai_name)
            now_ms = self._now_ms()
            self._pending[message_id] = now_ms

            # Stub DB outbound log
            self._log_outbound(ai_name, content, role, message_id, now_ms)

            # Emit user message to UI immediately for this target
            self.user_message_signal.emit(ai_name, content)

            handler = self.providers[ai_name]

            # Schedule provider call with stagger to avoid thread storms
            def _invoke_provider(name=ai_name, msg=content, r=role, mid=message_id):
                handler_ref = self.providers.get(name)
                if handler_ref:
                    handler_ref(msg, r)

            QTimer.singleShot(delay_ms, _invoke_provider)
            delay_ms += step_ms

    # ---------- PROVIDER CALLBACK ENTRY ----------

    def on_provider_response(self, ai_name: str, content: str, message_id: str):
        """
        Providers MUST call this when they have a response.
        This is the single choke point for:
          - response time tracking
          - DB logging
          - UI signal emission
        """
        now_ms = self._now_ms()
        start_ms = self._pending.pop(message_id, now_ms)
        response_time_ms = max(0, now_ms - start_ms)

        # Stub DB inbound log
        self._log_inbound(ai_name, content, message_id, now_ms, response_time_ms)

        # Hook for future analytics / routing
        self.on_response_received(ai_name, content, response_time_ms)

        # Emit to UI
        self.response_signal.emit(ai_name, content)

    def on_provider_chunk(self, ai_name: str, chunk: str):
        """Called by streaming providers for each token chunk."""
        self.chunk_signal.emit(ai_name, chunk)

    # ---------- HOOK FOR FUTURE ANALYTICS ----------

    def on_response_received(self, ai_name: str, content: str, response_time_ms: int):
        """
        Phase 1: no‑op.
        Phase 2+: can feed:
          - latency dashboards
          - adaptive routing
          - AI performance metrics
        """
        pass

    # ---------- INTERNAL HELPERS ----------

    def _now_ms(self) -> int:
        return int(QDateTime.currentDateTimeUtc().toMSecsSinceEpoch())

    def _make_message_id(self, ai_name: str) -> str:
        # Simple unique ID: ai_name + timestamp
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
