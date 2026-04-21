# ui/prompt/target_selector.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QApplication,
    QSizePolicy,
)

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.column_manager import ColumnManager


# ------------------------------------------------------------
#  INDIVIDUAL MODEL SELECTOR  (TOP STRIP ONLY)
# ------------------------------------------------------------
class TargetSelector(QWidget):
    targets_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected = set()
        self.setFixedHeight(32)

        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        self.buttons = {
            "claude": self._make_btn("Claude"),
            "chatgpt": self._make_btn("ChatGPT"),
            "grok": self._make_btn("Grok"),
            "copilot": self._make_btn("Copilot"),
            "local": self._make_btn("Local"),
        }

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for btn in self.buttons.values():
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(btn)

        self.setLayout(layout)

    def _make_btn(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(28)
        btn.setFont(QFont("Segoe UI", 10))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("glow", True)
        btn.setProperty("kaijuRole", "targetButton")

        btn.clicked.connect(lambda checked, b=btn: self._on_clicked(b, checked))
        GlowManager().register_widget(btn, intensity="subtle")
        return btn

    def _on_clicked(self, btn: QPushButton, checked: bool):
        name = btn.text().lower()

        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            if checked:
                self.selected.add(name)
            else:
                self.selected.discard(name)
        else:
            if checked:
                self.selected = {name}
            else:
                self.selected = set()

            for key, b in self.buttons.items():
                b.setChecked(key == name if checked else False)

        self.targets_changed.emit(list(self.selected))


# ------------------------------------------------------------
#  GLOBAL ALL SELECTOR  (BOTTOM STRIP ONLY)
# ------------------------------------------------------------
class SelectAllButton(QWidget):
    all_selected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        self.btn = QPushButton("ALL")
        self.btn.setCheckable(False)
        self.btn.setFixedHeight(20)
        self.btn.setFont(QFont("Segoe UI", 9))
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setProperty("glow", True)
        self.btn.setProperty("kaijuRole", "selectAllButton")
        self.btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        GlowManager().register_widget(self.btn, intensity="subtle")

        self.btn.clicked.connect(self._emit_all)
        self.btn.clicked.connect(ColumnManager.instance().show_all)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.btn)

        self.setLayout(layout)

    def _emit_all(self):
        self.all_selected.emit()
