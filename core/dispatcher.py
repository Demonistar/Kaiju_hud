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

        self._round_active = False
        self._round_prompt = ""
        self._round_role = "user"
        self._round_responses: Dict[str, str | None] = {}
        self._round_expected = set()
        self._round_timed_out = set()
        self._round_finalized = False

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

        if role == "user":
            self._scroll_active_chat_panels_to_top()

        # Expand 'all'
        if "all" in targets:
            targets = list(self.providers.keys())

        # Fixed dispatch order
        dispatch_order = ["claude", "chatgpt", "grok", "copilot"]

        active_targets = []
        for ai_name in ["claude", "chatgpt", "grok", "copilot", "local"]:
            if ai_name in targets and ai_name in self.providers and ColumnManager.instance().is_active(ai_name):
                active_targets.append(ai_name)

        self._round_active = True
        self._round_prompt = content
        self._round_role = role
        self._round_expected = {
            ai_name for ai_name in ["claude", "chatgpt", "grok", "copilot"] if ai_name in active_targets
        }
        self._round_responses = {
            "claude": None,
            "chatgpt": None,
            "grok": None,
            "copilot": None,
        }
        for ai_name in ["claude", "chatgpt", "grok", "copilot"]:
            if ai_name not in self._round_expected:
                self._round_responses[ai_name] = ""
        self._round_timed_out = set()
        self._round_finalized = False

        local_handler = self.providers.get("local")
        if local_handler is not None and hasattr(local_handler, "__self__"):
            local_provider = local_handler.__self__
            if hasattr(local_provider, "_db"):
                session_id = str(self._now_ms())
                key_id = local_provider._db.open_round(session_id, content, active_targets)
                local_provider._current_key_id = key_id

        delay_ms = 0
        step_ms = 1500
        fired = []

        for ai_name in dispatch_order:
            if ai_name not in targets:
                continue
            if ai_name not in self.providers:
                continue

            if not ColumnManager.instance().is_active(ai_name):
                continue

            fired.append(ai_name)
            message_id = self._make_message_id(ai_name)
            now_ms = self._now_ms()
            self._pending[message_id] = now_ms

            self._log_outbound(ai_name, content, role, message_id, now_ms)
            self.user_message_signal.emit(ai_name, content)

            def _invoke_provider(name=ai_name, msg=content, r=role):
                handler_ref = self.providers.get(name)
                if handler_ref:
                    handler_ref(msg, r)

            QTimer.singleShot(delay_ms, _invoke_provider)
            delay_ms += step_ms

        if not fired:
            self._finalize_round()
            return

        def _start_timeouts(names=fired):
            for ai_name in names:
                QTimer.singleShot(300000, lambda name=ai_name: self._on_ai_timeout(name))

        QTimer.singleShot(delay_ms, _start_timeouts)

    # ---------- PROVIDER CALLBACKS ----------

    def on_provider_chunk(self, ai_name: str, chunk: str):
        """Providers call this for each streaming chunk."""
        self.chunk_signal.emit(ai_name, chunk)

    def on_provider_response(self, ai_name: str, content: str, message_id: str):
        """Providers call this when a full response is ready."""
        now_ms = self._now_ms()
        start_ms = self._pending.pop(message_id, now_ms)
        response_time_ms = max(0, now_ms - start_ms)

        self._log_inbound(ai_name, content, message_id, now_ms, response_time_ms)
        self.on_response_received(ai_name, content, response_time_ms)

        if self._round_active and ai_name in self._round_responses and not self._round_finalized:
            self._round_responses[ai_name] = content
            self._update_round_db(ai_name, content)
            self._try_finalize_round()

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

    def _on_ai_timeout(self, ai_name: str):
        if not self._round_active or self._round_finalized:
            return
        if self._round_responses.get(ai_name) is None:
            self._round_timed_out.add(ai_name)
            self._finalize_round()

    def _try_finalize_round(self):
        if all(self._round_responses.get(k) is not None for k in self._round_expected):
            self._finalize_round()

    def _finalize_round(self):
        if self._round_finalized:
            return
        self._round_finalized = True

        for ai_name in ["claude", "chatgpt", "grok", "copilot"]:
            if self._round_responses.get(ai_name) is None:
                self._round_responses[ai_name] = None

        context_block = (
            f"User prompt: {self._round_prompt}\n"
            f"Claude: {self._round_responses.get('claude')}\n"
            f"ChatGPT: {self._round_responses.get('chatgpt')}\n"
            f"Grok: {self._round_responses.get('grok')}\n"
            f"Copilot: {self._round_responses.get('copilot')}"
        )

        local_handler = self.providers.get("local")
        if local_handler:
            local_handler(context_block, self._round_role)

        self._round_active = False

    def _update_round_db(self, ai_name: str, content: str):
        local_handler = self.providers.get("local")
        if local_handler is None or not hasattr(local_handler, "__self__"):
            return
        local_provider = local_handler.__self__
        key_id = getattr(local_provider, "_current_key_id", None)
        if key_id is None:
            return

        col_map = {
            "claude": "claude_response",
            "chatgpt": "chatgpt_response",
            "grok": "grok_response",
            "copilot": "copilot_response",
        }
        col = col_map.get(ai_name)
        if col:
            local_provider._db.update_response(key_id, col, content)

    def _scroll_active_chat_panels_to_top(self):
        cm = ColumnManager.instance()
        widgets = getattr(cm, "_widgets", {})
        for ai_name in cm.active_columns():
            pair = widgets.get(ai_name)
            if not pair or len(pair) < 2:
                continue
            bottom_widget = pair[1]
            chat = getattr(bottom_widget, "chat", None)
            if chat is not None and hasattr(chat, "verticalScrollBar"):
                chat.verticalScrollBar().setValue(0)
