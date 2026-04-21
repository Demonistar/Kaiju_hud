# ui/global_ribbon/collapse_all.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from core.app_state import AppState
from core.glow_manager import GlowManager
from core.column_manager import ColumnManager


class CollapseAll(QWidget):
    collapse_all_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(120, 40)

        self.hovered = False
        self.pressed = False

        GlowManager().register_widget(self, intensity="medium")
        AppState.instance().theme_changed.connect(self.update)

        self.label = "Collapse All"

    # ---------------------------------------------------------
    # MOUSE EVENTS
    # ---------------------------------------------------------

    def enterEvent(self, event):
        self.hovered = True
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = True
            self.update()

    def mouseReleaseEvent(self, event):
        if self.pressed and event.button() == Qt.MouseButton.LeftButton:
            self.pressed = False
            self.update()
            self._toggle()

    # ---------------------------------------------------------
    # TOGGLE LOGIC (100% compatible with your ColumnManager)
    # ---------------------------------------------------------

    def _toggle(self):
        cm = ColumnManager.instance()

        # Any hidden?
        any_hidden = any(not v for v in cm.columns.values())

        if any_hidden:
            cm.show_all()
            self.label = "Collapse All"
        else:
            cm.hide_all()
            self.label = "Restore All"

        self.update()

    # ---------------------------------------------------------
    # PAINT EVENT
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.pressed:
            bg = QColor(50, 50, 50)
        elif self.hovered:
            bg = QColor(70, 70, 70)
        else:
            bg = QColor(40, 40, 40)

        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        painter.setPen(QColor(220, 220, 220))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.label)
