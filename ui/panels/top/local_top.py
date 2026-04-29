# ui/panels/top/local_top.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.column_manager import ColumnManager
from ui.widgets.local_eye_indicator import LocalEyeIndicator


class LocalTop(QFrame):
    relay_clicked = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    """
    Collapsible top panel for the Local column.
    Shows project name, session name, and status indicator.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(120)

        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        self.project_label = QLabel("Project: None")
        self.project_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        self.session_label = QLabel("Session: None")
        self.session_label.setFont(QFont("Segoe UI", 9))

        self.status_label = QLabel("●")
        self.status_label.setFont(QFont("Segoe UI", 14))
        self.status_label.setStyleSheet("color: #00FF88;")

        self.relay_btn = QPushButton("Relay")
        self.relay_btn.setFixedHeight(22)
        self.relay_btn.clicked.connect(lambda: self.relay_clicked.emit("local"))
        GlowManager().register_widget(self.relay_btn, intensity="subtle")

        self.collapse_btn = QPushButton("⮝")
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.clicked.connect(lambda: ColumnManager().toggle("local"))
        GlowManager().register_widget(self.collapse_btn, intensity="subtle")

        self.eye = LocalEyeIndicator()
        self.btn_observer = QPushButton("Observer")
        self.btn_participate = QPushButton("Participate")
        self.btn_command = QPushButton("Command")
        self.btn_observer.setFixedHeight(22)
        self.btn_participate.setFixedHeight(22)
        self.btn_command.setFixedHeight(22)
        self.btn_observer.clicked.connect(lambda: self._on_mode_change("observer"))
        self.btn_participate.clicked.connect(lambda: self._on_mode_change("participate"))
        self.btn_command.clicked.connect(lambda: self._on_mode_change("command"))

        left = QVBoxLayout()
        left.addWidget(self.project_label)
        left.addWidget(self.session_label)

        right = QVBoxLayout()
        right.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.relay_btn, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.collapse_btn, alignment=Qt.AlignmentFlag.AlignRight)

        row = QHBoxLayout()
        row.addLayout(left)
        row.addLayout(right)
        row.setContentsMargins(10, 5, 10, 5)

        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.btn_observer)
        toggle_row.addWidget(self.btn_participate)
        toggle_row.addWidget(self.btn_command)

        eye_row = QHBoxLayout()
        eye_row.addWidget(self.eye, alignment=Qt.AlignmentFlag.AlignRight)

        root = QVBoxLayout()
        root.addLayout(row)
        root.addLayout(toggle_row)
        root.addLayout(eye_row)

        self.setLayout(root)

        self._on_mode_change("observer")

    def _on_mode_change(self, mode: str):
        self.eye.set_mode(mode)
        self.mode_changed.emit(mode)
        for btn, m in [(self.btn_observer, "observer"), (self.btn_participate, "participate"), (self.btn_command, "command")]:
            btn.setStyleSheet("font-weight: bold; border: 1px solid #00F6FF;" if m == mode else "")

    def set_mode(self, mode: str):
        self._on_mode_change(mode)

    def set_project(self, name: str):
        self.project_label.setText(f"Project: {name}")

    def set_session(self, name: str):
        self.session_label.setText(f"Session: {name}")

    def set_status(self, active: bool):
        color = "#00FF88" if active else "#FF4444"
        self.status_label.setStyleSheet(f"color: {color};")
