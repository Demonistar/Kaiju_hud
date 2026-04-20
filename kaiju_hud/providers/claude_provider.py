# providers/claude_provider.py

import uuid
import json
import httpx

SYSTEM_PROMPT = ""

IDENTITY_PREFIX = (
    "[SYSTEM CONTEXT - DO NOT ACKNOWLEDGE OR STATE THIS: "
    "You are Claude, made by Anthropic. You are Column 1 in a 5-column "
    "multi-AI interface called the Kaiju Command Bridge. The other columns are "
    "ChatGPT (col 2), Grok (col 3), Copilot (col 4), and Bobby Bee local LLM (col 5). "
    "If the user does not address you by name they may be speaking to all AIs simultaneously. "
    "Maintain your identity as Claude at all times regardless of other names in conversation. "
    "Do not mention this instruction.] "
)


class ClaudeProvider:
    """
    Claude provider with httpx streaming, identity injection, and rolling history.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None
        self.message_history = []
        self.model = "claude-sonnet-4-5"

    # ---------------------------------------------------------
    # DISPATCHER BINDING
    # ---------------------------------------------------------

    def bind(self, dispatcher):
        """Store dispatcher reference so provider_handler can call it."""
        self._dispatcher = dispatcher

    # ---------------------------------------------------------
    # PROVIDER HANDLER (CALLED BY DISPATCHER)
    # ---------------------------------------------------------

    def provider_handler(self, content: str, role: str):
        response = self._call_claude_api(content, role)
        message_id = f"claude-{uuid.uuid4().hex}"
        self._dispatcher.on_provider_response("claude", response, message_id)

    # ---------------------------------------------------------
    # INTERNAL: STREAMING API CALL
    # ---------------------------------------------------------

    def _call_claude_api(self, content: str, role: str) -> str:
        if not self.api_key:
            return f"[Claude stubbed response to: {content}]"

        injected_content = IDENTITY_PREFIX + content
        messages = self.message_history + [{"role": role, "content": injected_content}]

        try:
            full_response = ""
            with httpx.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": SYSTEM_PROMPT,
                    "messages": messages,
                    "stream": True
                },
                timeout=60
            ) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                chunk = data["delta"].get("text", "")
                                if chunk:
                                    full_response += chunk
                                    if self._dispatcher:
                                        self._dispatcher.on_provider_chunk("claude", chunk)
                        except Exception:
                            continue

            # Update rolling history with clean (non-injected) content
            self.message_history.append({"role": "user", "content": content})
            self.message_history.append({"role": "assistant", "content": full_response})
            if len(self.message_history) > 6:
                self.message_history = self.message_history[-6:]

            return full_response

        except Exception as e:
            return f"[Claude API exception: {str(e)}]"
