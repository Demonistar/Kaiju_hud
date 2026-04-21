# ui/panels/top/chatgpt_top.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.column_manager import ColumnManager


class ChatGPTTop(QFrame):
    """
    Collapsible top panel for the ChatGPT column.
    Shows project name, session name, and status indicator.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(80)

        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        self.project_label = QLabel("Project: None")
        self.project_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        self.session_label = QLabel("Session: None")
        self.session_label.setFont(QFont("Segoe UI", 9))

        self.status_label = QLabel("●")
        self.status_label.setFont(QFont("Segoe UI", 14))
        self.status_label.setStyleSheet("color: #00FF88;")

        self.collapse_btn = QPushButton("⮝")
        self.collapse_btn.setFixedSize(28, 28)

        # FIXED: use the singleton
        self.collapse_btn.clicked.connect(
            lambda: ColumnManager.instance().toggle("chatgpt")
        )

        GlowManager().register_widget(self.collapse_btn, intensity="subtle")

        left = QVBoxLayout()
        left.addWidget(self.project_label)
        left.addWidget(self.session_label)

        right = QVBoxLayout()
        right.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.collapse_btn, alignment=Qt.AlignmentFlag.AlignRight)

        row = QHBoxLayout()
        row.addLayout(left)
        row.addLayout(right)
        row.setContentsMargins(10, 5, 10, 5)

        self.setLayout(row)

    # Public API
    def set_project(self, name):
        self.project_label.setText(f"Project: {name}")

    def set_session(self, name):
        self.session_label.setText(f"Session: {name}")

    def set_status(self, active: bool):
        color = "#00FF88" if active else "#FF4444"
        self.status_label.setStyleSheet(f"color: {color};")
