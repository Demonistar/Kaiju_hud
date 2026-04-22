# ui/global_ribbon/global_ribbon.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QApplication, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from ui.global_ribbon.mode_switch import ModeSwitch
from ui.global_ribbon.theme_switch import ThemeSwitch
from ui.global_ribbon.glow_switch import GlowSwitch
from ui.global_ribbon.collapse_all import CollapseAll

from core.app_state import AppState
from core.column_manager import ColumnManager


class GlobalRibbon(QWidget):
    db_view_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(48)

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.mode_switch = ModeSwitch()
        self.theme_switch = ThemeSwitch()
        self.glow_switch = GlowSwitch()
        self.collapse_all = CollapseAll()
        self.db_view_button = QPushButton("DB View")
        self.db_view_button.setFixedHeight(40)

        layout.addWidget(self.mode_switch)
        layout.addWidget(self.theme_switch)
        layout.addWidget(self.glow_switch)
        layout.addWidget(self.collapse_all)
        layout.addWidget(self.db_view_button)

        self.setLayout(layout)

        self.theme_switch.theme_changed.connect(AppState.instance().set_theme)
        self.glow_switch.glow_changed.connect(AppState.instance().set_glow)
        self.mode_switch.mode_changed.connect(self._on_mode_changed)
        self.collapse_all.collapse_all_clicked.connect(
            ColumnManager.instance().hide_all
        )
        self.db_view_button.clicked.connect(self.db_view_clicked.emit)

    def _on_mode_changed(self, mode: str):
        win = QApplication.instance().activeWindow()
        if not win:
            return

        if mode == "FS":
            win.showFullScreen()

        elif mode == "BL":
            win.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Window
            )
            win.show()

        elif mode == "WI":
            win.setWindowFlags(Qt.WindowType.Window)
            win.showNormal()
