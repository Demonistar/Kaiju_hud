# core/dispatcher.py

from PyQt6.QtCore import QObject, pyqtSignal, QDateTime, QTimer
from typing import List, Dict, Callable
from core.column_manager import ColumnManager
from core.settings_manager import SettingsManager


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
        self._round_synthesis_sent = False
        self._settings = SettingsManager()
        self._latest_ai_responses: Dict[str, str] = {}

    # ---------- PUBLIC API ----------

    def register_provider(self, ai_name: str, handler: Callable[[str, str], None]):
        """Register a provider handler."""
        self.providers[ai_name] = handler

    def send_message(self, targets: List[str], display_content: str, provider_content: str | None = None, role: str = "user"):
        """
        Core entry point for sending messages to providers.
        Implements:
          - user_message_signal
          - sequential dispatch (1.5s)
          - collapsed column auto-exclusion
        """
        if not targets:
            return

        if provider_content is None:
            provider_content = display_content

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
        self._round_prompt = display_content
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
        self._round_synthesis_sent = False
        self._settings = SettingsManager()

        local_handler = self.providers.get("local")
        if local_handler is not None and hasattr(local_handler, "__self__"):
            local_provider = local_handler.__self__
            if hasattr(local_provider, "_db"):
                session_id = str(self._now_ms())
                key_id = local_provider._db.open_round(session_id, display_content, active_targets)
                local_provider._current_key_id = key_id

        if role == "user" and "local" in active_targets:
            self.user_message_signal.emit("local", display_content)
            local_message_id = self._make_message_id("local")
            now_ms = self._now_ms()
            self._log_outbound("local", display_content, role, local_message_id, now_ms)

            def _invoke_local_direct(msg=display_content, r=role):
                handler_ref = self.providers.get("local")
                if handler_ref:
                    should_track_pending = True
                    if hasattr(handler_ref, "__self__"):
                        local_provider = handler_ref.__self__
                        if hasattr(local_provider, "should_emit_user_response"):
                            should_track_pending = bool(local_provider.should_emit_user_response(r))
                    if should_track_pending:
                        self._pending[local_message_id] = now_ms
                    handler_ref(msg, r)

            QTimer.singleShot(0, _invoke_local_direct)

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

            outbound_content = provider_content if ai_name in ["claude", "chatgpt", "grok", "copilot"] else display_content

            self._log_outbound(ai_name, outbound_content, role, message_id, now_ms)
            self.user_message_signal.emit(ai_name, display_content)

            def _invoke_provider(name=ai_name, msg=outbound_content, r=role):
                handler_ref = self.providers.get(name)
                if handler_ref:
                    handler_ref(msg, r)

            QTimer.singleShot(delay_ms, _invoke_provider)
            delay_ms += step_ms

        if role == "user":
            self._scroll_active_chat_panels_to_top()

        if not fired:
            self._finalize_round()
            return

        def _start_timeouts(names=fired):
            for ai_name in names:
                QTimer.singleShot(300000, lambda name=ai_name: self._on_ai_timeout(name))

        QTimer.singleShot(delay_ms, _start_timeouts)


    def relay_last_response(self, source_ai: str, selected_targets: List[str]):
        if not source_ai:
            return
        source_text = self._latest_relayable_response(source_ai)
        if not source_text:
            return
        targets = [t for t in selected_targets if t != source_ai]
        self.relay_ai_response(source_ai, source_text, targets)

    def relay_ai_response(self, source_ai: str, source_text: str, target_list: List[str]):
        if not source_text or not target_list:
            return
        source_label_map = {
            "claude": "Claude",
            "chatgpt": "ChatGPT",
            "grok": "Grok",
            "copilot": "Copilot",
            "local": "Local",
        }
        source_label = source_label_map.get(source_ai, source_ai)
        active_targets = [ai_name for ai_name in ["claude", "chatgpt", "grok", "copilot", "local"] if ai_name in target_list and ai_name in self.providers and ColumnManager.instance().is_active(ai_name)]
        if not active_targets:
            return
        wrapped_prompt = (
            "You are receiving an output from another AI in the Kaiju Command Bridge.\n\n"
            f"Source AI: {source_label}\n\n"
            "Your task:\n"
            "- Analyze the source AI’s response\n"
            "- Identify what is valuable or correct\n"
            "- Identify anything you disagree with\n"
            "- Identify missing context, risks, or weak assumptions\n"
            "- Recommend improvements or alternatives, especially if they contradict the source response\n\n"
            "Do not respond to the source AI directly.\n"
            "Respond to the user with your analysis.\n\n"
            "--- BEGIN SOURCE AI RESPONSE ---\n"
            f"{source_text}\n"
            "--- END SOURCE AI RESPONSE ---"
        )
        hidden_suffix = ""
        if self._settings.get_hidden_prompt_enabled():
            profile = self._settings.get_hidden_prompt_profile()
            hidden_suffix = self._settings.get_hidden_prompt_text(profile).strip()
        provider_content = wrapped_prompt if not hidden_suffix else f"{wrapped_prompt}\n\n{hidden_suffix}"
        now_ms = self._now_ms()
        for ai_name in active_targets:
            message_id = self._make_message_id(ai_name)
            self._pending[message_id] = now_ms
            self._log_outbound(ai_name, provider_content, "relay", message_id, now_ms)
            handler_ref = self.providers.get(ai_name)
            if handler_ref:
                handler_ref(provider_content, "relay")

    def _latest_relayable_response(self, ai_name: str) -> str:
        content = (self._latest_ai_responses.get(ai_name) or "").strip()
        if not content:
            return ""
        if ai_name == "local":
            status_prefixes = ("[NOTICE]", "[Reading]", "[Filing]", "[Cataloging]", "[Thinking]", "[Notes]")
            if any(content.startswith(prefix) for prefix in status_prefixes):
                return ""
        return content

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
        self._latest_ai_responses[ai_name] = content
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

        # Provider-only synthesis context (no user prompt / task directives).
        provider_context_parts = []
        for ai_name in ["claude", "chatgpt", "grok", "copilot"]:
            value = self._round_responses.get(ai_name)
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    provider_context_parts.append(cleaned)
        context_block = "\n\n".join(provider_context_parts)

        local_handler = self.providers.get("local")
        should_trigger = True
        if local_handler is not None and hasattr(local_handler, "__self__"):
            local_provider = local_handler.__self__
            if hasattr(local_provider, "should_synthesize_on_round_complete"):
                should_trigger = bool(local_provider.should_synthesize_on_round_complete())

        if local_handler and should_trigger and context_block.strip() and not self._round_synthesis_sent:
            self._round_synthesis_sent = True
            local_handler(context_block, "synthesis")

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
