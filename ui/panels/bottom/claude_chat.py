# ui/panels/bottom/claude_chat.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextOption, QTextCursor
from PyQt6.QtWidgets import QFrame, QTextEdit, QVBoxLayout
import re

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.dispatcher import Dispatcher
from markdown import markdown


class ClaudeChat(QFrame):
    MAX_BLOCKS = 500
    MAX_CHARS = 200_000

    def __init__(self, dispatcher: Dispatcher, parent=None):
        super().__init__(parent)

        self.dispatcher = dispatcher
        self.setFrameShape(QFrame.Shape.StyledPanel)

        GlowManager().register_widget(self, intensity="subtle")
        AppState.instance().theme_changed.connect(self.update)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setFont(QFont("Segoe UI", 10))
        self.chat.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.chat.setStyleSheet("QTextEdit { background-color: #0d1117; color: #A0E0FF; border: 1px solid #A0E0FF; }")
        self.chat.document().setDefaultStyleSheet(
            "body { color: #A0E0FF; }"
            "p { margin: 0 0 6px 0; padding: 0; color: #A0E0FF; }"
            "ul { margin: 0; padding-left: 16px; }"
            "ol { margin: 0; padding-left: 16px; }"
            "h1, h2, h3 { margin: 4px 0; color: #A0E0FF; }"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.chat)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self._streaming_buffer = ""
        self._is_streaming = False

        self.dispatcher.response_signal.connect(self._on_response)
        self.dispatcher.user_message_signal.connect(self._on_user_message)
        self.dispatcher.chunk_signal.connect(self._on_chunk)

    def _safe_append(self, html: str):
        doc = self.chat.document()

        while doc.blockCount() > self.MAX_BLOCKS:
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        if doc.characterCount() > self.MAX_CHARS:
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.Document)
            cursor.removeSelectedText()
            self.chat.append("<i>[Chat trimmed due to size]</i>")

        self.chat.append(html)
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _render_markdown(self, content: str) -> str:
        html = markdown(content, extensions=["fenced_code", "tables"])
        html = re.sub(r'^<p>(.*?)</p>', r'\1', html, count=1, flags=re.DOTALL)
        return html

    def _on_user_message(self, ai_name, content):
        if ai_name != "claude":
            return
        self._safe_append(f'<span style="color:#E0E0E0"><b>YOU:</b> {content}</span>')
        self._streaming_buffer = ""
        self._is_streaming = True

    def _on_chunk(self, ai_name, chunk):
        if ai_name != "claude":
            return

        if not self._streaming_buffer:
            self._safe_append('<span style="color:#A0E0FF"><b>CLAUDE:</b></span> ')
            cursor = self.chat.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.chat.setTextCursor(cursor)

        self._streaming_buffer += chunk
        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat.setTextCursor(cursor)
        self.chat.insertPlainText(chunk)
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _on_response(self, ai_name, content):
        if ai_name != "claude":
            return

        if self._is_streaming and self._streaming_buffer:
            self._is_streaming = False
            self._streaming_buffer = ""
            self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
            return

        self._is_streaming = False
        self._streaming_buffer = ""

        html = self._render_markdown(content)
        self._safe_append(f'<span style="color:#A0E0FF"><b>CLAUDE:</b></span> {html}')