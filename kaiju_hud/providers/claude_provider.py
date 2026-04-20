# providers/claude_provider.py

import uuid
import requests


class ClaudeProvider:
    """
    Phase 1 Claude provider using the bind() pattern.
    Phase 2 will use message_history for conversation context.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None

        # Phase 2: conversation context
        self.message_history = []

        # Updated model name
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
        """
        Dispatcher calls this as:
            handler(content, role)
        """
        response = self._call_claude_api(content, role)

        # Generate unique message ID
        message_id = f"claude-{uuid.uuid4().hex}"

        # Send back to dispatcher
        self._dispatcher.on_provider_response("claude", response, message_id)

    # ---------------------------------------------------------
    # INTERNAL: API CALL (PHASE 1)
    # ---------------------------------------------------------

    def _call_claude_api(self, content: str, role: str) -> str:
        """
        Phase 1: Real API call if api_key is provided.
        Otherwise return a stubbed response.
        """

        if not self.api_key:
            return f"[Claude stubbed response to: {content}]"

        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

            payload = {
                "model": self.model,
                "max_tokens": 512,
                "messages": [
                    {"role": role, "content": content}
                ]
            }

            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=60
            )

            if resp.status_code != 200:
                return f"[Claude API error: HTTP {resp.status_code}]"

            data = resp.json()
            blocks = data.get("content", [])
            if not blocks:
                return "[Claude API error: empty response]"

            return blocks[0].get("text", "")

        except Exception as e:
            return f"[Claude API exception: {str(e)}]"
