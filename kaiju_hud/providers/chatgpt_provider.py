# providers/chatgpt_provider.py

import uuid
import requests


class ChatGPTProvider:
    """
    Phase 1 ChatGPT provider using the bind() pattern.
    Phase 2 will use message_history for conversation context.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None

        # Phase 2: conversation context
        self.message_history = []

        # Default model for Phase 1
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
        """
        Dispatcher calls this as:
            handler(content, role)
        """
        response = self._call_openai_api(content, role)

        # Generate unique message ID
        message_id = f"chatgpt-{uuid.uuid4().hex}"

        # Send back to dispatcher
        self._dispatcher.on_provider_response("chatgpt", response, message_id)

    # ---------------------------------------------------------
    # INTERNAL: API CALL (PHASE 1)
    # ---------------------------------------------------------

    def _call_openai_api(self, content: str, role: str) -> str:
        """
        Phase 1: Real API call if api_key is provided.
        Otherwise return a stubbed response.

        NOTE:
        OpenAI returns:
            choices[0].message.content
        NOT Anthropic's blocks list.
        """

        if not self.api_key:
            return f"[ChatGPT stubbed response to: {content}]"

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
                "max_tokens": 512
            }

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            if resp.status_code != 200:
                return f"[ChatGPT API error: HTTP {resp.status_code}]"

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return "[ChatGPT API error: empty response]"

            # Correct OpenAI structure:
            # choices[0].message.content
            return choices[0]["message"]["content"]

        except Exception as e:
            return f"[ChatGPT API exception: {str(e)}]"
