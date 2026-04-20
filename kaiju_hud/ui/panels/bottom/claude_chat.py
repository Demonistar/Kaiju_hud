# ui/panels/bottom/claude_chat.py

from PyQt6.QtGui import QFont, QTextOption
from PyQt6.QtWidgets import QFrame, QTextEdit, QVBoxLayout

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.dispatcher import Dispatcher


class ClaudeChat(QFrame):
    """
    Read-only chat history panel for Claude.
    """

    MAX_BLOCKS = 500        # hard scrollback limit
    MAX_CHARS = 200_000     # safety cap to prevent memory ballooning

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

        layout = QVBoxLayout()
        layout.addWidget(self.chat)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.dispatcher.response_signal.connect(self._on_response)
        self.dispatcher.user_message_signal.connect(self._on_user_message)
        self.dispatcher.chunk_signal.connect(self._on_chunk)
        self._streaming_buffer = ""
        self._is_streaming = False

    # ---------------------------------------------------------
    # SAFE APPEND LOGIC
    # ---------------------------------------------------------

    def _safe_append(self, html: str):
        """Append HTML safely with scrollback + memory protection."""

        doc = self.chat.document()

        # 1. Scrollback limit (remove oldest blocks)
        while doc.blockCount() > self.MAX_BLOCKS:
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        # 2. Hard character limit
        if doc.characterCount() > self.MAX_CHARS:
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.Document)
            cursor.removeSelectedText()
            self.chat.append("<i>[Chat trimmed due to size]</i>")

        # 3. Append new content
        self.chat.append(html)

        # 4. Auto-scroll
        self.chat.verticalScrollBar().setValue(
            self.chat.verticalScrollBar().maximum()
        )

    # ---------------------------------------------------------
    # DISPATCHER CALLBACKS
    # ---------------------------------------------------------

    def _on_user_message(self, ai_name, content):
        if ai_name != "claude":
            return
        html = f'<span style="color:#FFFFFF"><b>YOU:</b> {content}</span>'
        self._safe_append(html)
        self._streaming_buffer = ""
        self._is_streaming = True

    def _on_chunk(self, ai_name, chunk):
        if ai_name != "claude":
            return
        self._streaming_buffer += chunk
        cursor = self.chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat.setTextCursor(cursor)
        self.chat.insertPlainText(chunk)
        self.chat.verticalScrollBar().setValue(
            self.chat.verticalScrollBar().maximum()
        )

    def _on_response(self, ai_name, content):
        if ai_name != "claude":
            return
        if self._is_streaming:
            self._is_streaming = False
            self._streaming_buffer = ""
            self.chat.verticalScrollBar().setValue(
                self.chat.verticalScrollBar().maximum()
            )
            return
        # Non-streaming fallback
        prefix_color = "#A0E0FF"
        prefix_name = "CLAUDE"
        html = f'<span style="color:{prefix_color}"><b>{prefix_name}:</b></span> {content}'
        self._safe_append(html)
