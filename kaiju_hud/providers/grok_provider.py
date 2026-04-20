import uuid
import requests
import json
from typing import Optional, List, Dict, Generator

class GrokProvider:
    """
    Grok provider for your 5-AI HUD.
    - Uses grok-4.20-0309-reasoning by default (strong reasoning + uncensored)
    - Supports streaming for smooth HUD updates
    - Your local LLM can switch models as needed
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None

        # Conversation context (Phase 2)
        self.message_history: List[Dict] = []

        # Default to the strong uncensored reasoning model
        self.model = "grok-4.20-0309-reasoning"

        # Base URL
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
        """
        Main entry point from your dispatcher.
        Now supports streaming.
        """
        if not self.api_key:
            stub = f"[Grok stubbed response to: {content}]"
            self._dispatcher.on_provider_response("grok", stub, f"grok-{uuid.uuid4().hex}")
            return

        # For Phase 2: you can append to history here if you want persistent context
        # self.message_history.append({"role": role, "content": content})

        response_text = self._call_grok_api_stream(content, role)

        message_id = f"grok-{uuid.uuid4().hex}"
        self._dispatcher.on_provider_response("grok", response_text, message_id)

    # ------------------------------------------------------
    # STREAMING API CALL (Recommended for HUD)
    # ------------------------------------------------------
    def _call_grok_api_stream(self, content: str, role: str) -> str:
        """Returns full response as string, but streams internally for smooth UI"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": role, "content": content}
                ],
                "max_tokens": 1024,          # Increased for better responses
                "temperature": 0.85,         # Good balance for creative/uncensored output
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
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                full_response += delta
                                # Optional: You can send partial chunks to dispatcher for live typing effect
                                # self._dispatcher.on_partial_response("grok", delta)
                        except:
                            pass

            return full_response if full_response else "[Empty response from Grok]"

        except Exception as e:
            return f"[Grok API exception: {str(e)}]"

    # ------------------------------------------------------
    # Simple non-streaming fallback (if needed)
    # ------------------------------------------------------
    def _call_grok_api(self, content: str, role: str) -> str:
        """Non-streaming version - kept for compatibility"""
        # For now just call the streaming version and return full text
        return self._call_grok_api_stream(content, role)