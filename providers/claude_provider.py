# providers/claude_provider.py

import uuid
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.file_broker import FileBroker

FILE_SYSTEM_PREFIX = """You have direct read/write access to the Kaiju HUD project at D:\\AI\\kaiju_hud via FileBroker.

To read a file, respond with exactly:
READ: path/to/file.py

To write a file, respond with exactly:
WRITE: path/to/file.py
<<<FILE_CONTENT>>>
(complete file contents here)
<<<END>>>

You can chain multiple READ and WRITE commands in one response.
The HUD will execute them and show you the results.
Project root: D:\\AI\\kaiju_hud
"""


class ClaudeWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, api_key, model, content, role, max_retries, base_backoff):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.content = content
        self.role = role
        self.max_retries = max_retries
        self.base_backoff = base_backoff

    def run(self):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": self.role, "content": self.content}]
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=300
                )

                if resp.status_code == 529:
                    time.sleep(self.base_backoff * (2 ** attempt))
                    continue

                if resp.status_code != 200:
                    message_id = f"claude-{uuid.uuid4().hex}"
                    self.finished.emit(f"[Claude API error: HTTP {resp.status_code}]", message_id)
                    return

                data = resp.json()
                blocks = data.get("content", [])
                text = blocks[0].get("text", "") if blocks else ""

                if not text:
                    time.sleep(self.base_backoff * (2 ** attempt))
                    continue

                message_id = f"claude-{uuid.uuid4().hex}"
                self.finished.emit(text, message_id)
                return

            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_backoff * (2 ** attempt))
                    continue
                message_id = f"claude-{uuid.uuid4().hex}"
                self.finished.emit(f"[Claude API exception: {str(e)}]", message_id)
                return

        message_id = f"claude-{uuid.uuid4().hex}"
        self.finished.emit("[Claude API error: max retries exceeded]", message_id)


class ClaudeProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._dispatcher = None
        self.message_history = []
        self.model = "claude-sonnet-4-5"
        self.max_retries = 3
        self.base_backoff = 1.0
        self._worker = None
        self._broker = FileBroker()
        self._build_mode = True

    def bind(self, dispatcher):
        self._dispatcher = dispatcher

    def set_build_mode(self, enabled: bool):
        self._build_mode = enabled

    def provider_handler(self, content: str, role: str):
        if not self.api_key:
            message_id = f"claude-{uuid.uuid4().hex}"
            self._dispatcher.on_provider_response("claude", f"[Claude stubbed response to: {content}]", message_id)
            return

        if self._build_mode:
            content = FILE_SYSTEM_PREFIX + "\n\n" + content

        self._worker = ClaudeWorker(
            self.api_key, self.model, content, role,
            self.max_retries, self.base_backoff
        )
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _on_worker_done(self, response: str, message_id: str):
        processed = self._handle_file_ops(response)
        if self._dispatcher:
            self._dispatcher.on_provider_response("claude", processed, message_id)

    def _handle_file_ops(self, response: str) -> str:
        if "READ:" not in response and "WRITE:" not in response:
            return response

        lines = response.split("\n")
        output_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            if line.startswith("READ:"):
                path = line[5:].strip()
                content = self._broker.read(path)
                output_lines.append(f"[READ: {path}]\n{content}")
                i += 1

            elif line.startswith("WRITE:"):
                path = line[6:].strip()
                i += 1
                file_lines = []
                if i < len(lines) and lines[i].strip() == "<<<FILE_CONTENT>>>":
                    i += 1
                while i < len(lines) and lines[i].strip() != "<<<END>>>":
                    file_lines.append(lines[i])
                    i += 1
                i += 1
                result = self._broker.write(path, "\n".join(file_lines))
                output_lines.append(f"[{result}]")

            else:
                output_lines.append(line)
                i += 1

        return "\n".join(output_lines)