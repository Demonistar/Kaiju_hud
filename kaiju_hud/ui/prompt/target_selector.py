# ui/prompt/target_selector.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QApplication

from core.glow_manager import GlowManager
from core.app_state import AppState


class TargetSelector(QWidget):
    """
    Multi-target selector for AI dispatch.
    Pure UI widget:
      - No dispatcher logic
      - No prompt logic
      - Emits targets_changed(list)
      - Shift-click multi-select
      - Select All button
    """

    targets_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(40)

        # Track selected targets
        self.selected = set()

        # Glow + theme aware
        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        # -----------------------------------------------------
        # BUTTONS
        # -----------------------------------------------------
        self.buttons = {
            "claude": self._make_btn("Claude"),
            "chatgpt": self._make_btn("ChatGPT"),
            "grok": self._make_btn("Grok"),
            "copilot": self._make_btn("Copilot"),
            "local": self._make_btn("Local"),
        }

        self.select_all_btn = self._make_btn("All")
        self.select_all_btn.clicked.connect(self._select_all)

        # -----------------------------------------------------
        # LAYOUT
        # -----------------------------------------------------
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        for btn in self.buttons.values():
            layout.addWidget(btn)

        layout.addWidget(self.select_all_btn)
        self.setLayout(layout)

    # ---------------------------------------------------------
    # BUTTON CREATION
    # ---------------------------------------------------------

    def _make_btn(self, label):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(32)
        btn.setFont(QFont("Segoe UI", 10))
        btn.clicked.connect(lambda checked, b=btn: self._on_clicked(b, checked))
        GlowManager().register_widget(btn, intensity="subtle")
        return btn

    # ---------------------------------------------------------
    # CLICK HANDLING
    # ---------------------------------------------------------

    def _on_clicked(self, btn, checked):
        name = btn.text().lower()

        # Shift-click = multi-select
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            if checked:
                self.selected.add(name)
            else:
                self.selected.discard(name)

        else:
            # Normal click = single select
            if checked:
                self.selected = {name}
            else:
                self.selected = set()

            # Update button states
            for key, b in self.buttons.items():
                b.setChecked(key == name if checked else False)

        self._emit()

    def _select_all(self):
        self.selected = set(self.buttons.keys())
        for b in self.buttons.values():
            b.setChecked(True)
        self._emit()

    # ---------------------------------------------------------
    # EMIT TARGET LIST
    # ---------------------------------------------------------

    def _emit(self):
        self.targets_changed.emit(list(self.selected))
