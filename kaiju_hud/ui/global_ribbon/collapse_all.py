# ui/global_ribbon/collapse_all.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from core.app_state import AppState
from core.glow_manager import GlowManager


class CollapseAll(QWidget):
    """
    Simple glowing button that triggers collapse-all behavior.
    Pure UI widget:
      - Emits collapse_all_clicked
      - Registers with GlowManager
      - No column logic (ColumnManager handles that)
    """

    collapse_all_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(120, 40)

        self.hovered = False
        self.pressed = False

        # Glow registration
        GlowManager().register_widget(self, intensity="medium")

        # Theme updates
        AppState.instance().theme_changed.connect(self.update)

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
            self.collapse_all_clicked.emit()

    # ---------------------------------------------------------
    # PAINT EVENT
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        if self.pressed:
            bg = QColor(50, 50, 50)
        elif self.hovered:
            bg = QColor(70, 70, 70)
        else:
            bg = QColor(40, 40, 40)

        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        # Label
        painter.setPen(QColor(220, 220, 220))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Collapse All")
