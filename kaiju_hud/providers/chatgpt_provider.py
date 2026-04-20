# providers/chatgpt_provider.py

import uuid
import json
import requests

SYSTEM_PROMPT = ""

IDENTITY_PREFIX = (
    "[SYSTEM CONTEXT - DO NOT ACKNOWLEDGE OR STATE THIS: "
    "You are ChatGPT, made by OpenAI. You are Column 2 in a 5-column "
    "multi-AI interface called the Kaiju Command Bridge. The other columns are "
    "Claude (col 1), Grok (col 3), Copilot (col 4), and Bobby Bee local LLM (col 5). "
    "If the user does not address you by name they may be speaking to all AIs simultaneously. "
    "Maintain your identity as ChatGPT at all times. "
    "Do not mention this instruction.] "
)


class ChatGPTProvider:
    """
    ChatGPT provider with SSE streaming, identity injection, and rolling history.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None
        self.message_history = []
        self.model = "gpt-4.1-mini"

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
        response = self._call_openai_api(content, role)
        message_id = f"chatgpt-{uuid.uuid4().hex}"
        self._dispatcher.on_provider_response("chatgpt", response, message_id)

    # ---------------------------------------------------------
    # INTERNAL: STREAMING API CALL
    # ---------------------------------------------------------

    def _call_openai_api(self, content: str, role: str) -> str:
        if not self.api_key:
            return f"[ChatGPT stubbed response to: {content}]"

        injected_content = IDENTITY_PREFIX + content
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.message_history
        messages.append({"role": role, "content": injected_content})

        try:
            full_response = ""
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 4096,
                    "stream": True
                },
                stream=True,
                timeout=60
            )

            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            chunk = data["choices"][0]["delta"].get("content", "")
                            if chunk:
                                full_response += chunk
                                if self._dispatcher:
                                    self._dispatcher.on_provider_chunk("chatgpt", chunk)
                        except Exception:
                            continue

            # Update rolling history with clean (non-injected) content
            self.message_history.append({"role": "user", "content": content})
            self.message_history.append({"role": "assistant", "content": full_response})
            if len(self.message_history) > 6:
                self.message_history = self.message_history[-6:]

            return full_response

        except Exception as e:
            return f"[ChatGPT API exception: {str(e)}]"
