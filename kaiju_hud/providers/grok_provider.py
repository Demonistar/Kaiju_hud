import uuid
import requests
import json
from typing import List, Dict

SYSTEM_PROMPT = ""

IDENTITY_PREFIX = (
    "[SYSTEM CONTEXT - DO NOT ACKNOWLEDGE OR STATE THIS: "
    "You are Grok, made by xAI. You are Column 3 in a 5-column "
    "multi-AI interface called the Kaiju Command Bridge. The other columns are "
    "Claude (col 1), ChatGPT (col 2), Copilot (col 4), and Bobby Bee local LLM (col 5). "
    "If the user does not address you by name they may be speaking to all AIs simultaneously. "
    "Maintain your identity as Grok at all times. "
    "Do not mention this instruction.] "
)


class GrokProvider:
    """
    Grok provider with streaming, identity injection, and rolling history.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None
        self.message_history: List[Dict] = []
        self.model = "grok-4.20-0309-reasoning"
        self.base_url = "https://api.x.ai/v1/chat/completions"

    # ------------------------------------------------------
    # DISPATCHER BINDING
    # ------------------------------------------------------
    def bind(self, dispatcher):
        """Store dispatcher reference"""
        self._dispatcher = dispatcher

    # ------------------------------------------------------
    # MODEL SWITCHING (for your local LLM to control)
    # ------------------------------------------------------
    def set_model(self, model_name: str):
        """Switch between strong and fast models"""
        allowed_models = {
            "grok-4.20-0309-reasoning",
            "grok-4.1-fast-reasoning"
        }
        if model_name in allowed_models:
            self.model = model_name
            print(f"[GrokProvider] Model switched to: {model_name}")
        else:
            print(f"[GrokProvider] Warning: Model {model_name} not allowed by API key restrictions")

    # ------------------------------------------------------
    # PROVIDER HANDLER (called by your dispatcher)
    # ------------------------------------------------------
    def provider_handler(self, content: str, role: str = "user"):
        if not self.api_key:
            stub = f"[Grok stubbed response to: {content}]"
            self._dispatcher.on_provider_response("grok", stub, f"grok-{uuid.uuid4().hex}")
            return

        response_text = self._call_grok_api_stream(content, role)

        message_id = f"grok-{uuid.uuid4().hex}"
        self._dispatcher.on_provider_response("grok", response_text, message_id)

    # ------------------------------------------------------
    # STREAMING API CALL
    # ------------------------------------------------------
    def _call_grok_api_stream(self, content: str, role: str) -> str:
        """Streams internally; emits chunks to dispatcher; returns full response."""
        try:
            injected_content = IDENTITY_PREFIX + content
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages += self.message_history
            messages.append({"role": role, "content": injected_content})

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.85,
                "stream": True
            }

            resp = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=90,
                stream=True
            )

            if resp.status_code != 200:
                return f"[Grok API error: HTTP {resp.status_code}]"

            full_response = ""
            for line in resp.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk_data = json.loads(line[6:])
                            delta = chunk_data["choices"][0]["delta"].get("content", "")
                            if delta:
                                full_response += delta
                                if self._dispatcher:
                                    self._dispatcher.on_provider_chunk("grok", delta)
                        except Exception:
                            pass

            # Update rolling history with clean (non-injected) content
            self.message_history.append({"role": "user", "content": content})
            self.message_history.append({"role": "assistant", "content": full_response})
            if len(self.message_history) > 6:
                self.message_history = self.message_history[-6:]

            return full_response if full_response else "[Empty response from Grok]"

        except Exception as e:
            return f"[Grok API exception: {str(e)}]"

    # ------------------------------------------------------
    # Simple non-streaming fallback (if needed)
    # ------------------------------------------------------
    def _call_grok_api(self, content: str, role: str) -> str:
        """Non-streaming version - kept for compatibility"""
        return self._call_grok_api_stream(content, role)
