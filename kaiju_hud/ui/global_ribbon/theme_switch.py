# ui/global_ribbon/theme_switch.py

from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtSignal, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from core.app_state import AppState
from core.glow_manager import GlowManager


class ThemeSwitch(QWidget):
    """
    Three‑state sliding switch for theme selection:
      Classic / Meltdown / Halloween

    Pure UI widget:
      - Emits theme_changed(str)
      - Updates AppState.theme
      - Animated sliding knob
    """

    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(240, 40)

        self.app_state = AppState.instance()
        self.current_theme = self.app_state.theme()  # classic / meltdown / halloween

        # Knob animation
        self._knob_x = 0
        self.anim = QPropertyAnimation(self, b"knob_x")
        self.anim.setDuration(200)

        # Glow registration
        GlowManager().register_widget(self, intensity="medium")

        # Theme updates
        self.app_state.theme_changed.connect(self.update)

        self._update_knob_position(initial=True)

    # ---------------------------------------------------------
    # ANIMATABLE PROPERTY
    # ---------------------------------------------------------

    def get_knob_x(self):
        return self._knob_x

    def set_knob_x(self, value):
        self._knob_x = value
        self.update()

    knob_x = pyqtProperty(float, fget=get_knob_x, fset=set_knob_x)

    # ---------------------------------------------------------
    # THEME CHANGE
    # ---------------------------------------------------------

    def set_theme(self, theme: str):
        if theme not in ("classic", "meltdown", "halloween"):
            return

        self.current_theme = theme
        self.app_state.set_theme(theme)
        self.theme_changed.emit(theme)
        self._update_knob_position()

    # ---------------------------------------------------------
    # INTERNAL: KNOB POSITION
    # ---------------------------------------------------------

    def _update_knob_position(self, initial=False):
        positions = {
            "classic": 0,
            "meltdown": 80,
            "halloween": 160
        }

        target = positions.get(self.current_theme, 0)

        if initial:
            self._knob_x = target
        else:
            self.anim.stop()
            self.anim.setStartValue(self._knob_x)
            self.anim.setEndValue(target)
            self.anim.start()

        self.update()

    # ---------------------------------------------------------
    # MOUSE HANDLING
    # ---------------------------------------------------------

    def mousePressEvent(self, event):
        x = event.position().x()

        if x < 80:
            self.set_theme("classic")
        elif x < 160:
            self.set_theme("meltdown")
        else:
            self.set_theme("halloween")

    # ---------------------------------------------------------
    # PAINT EVENT
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background bar
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 240, 40, 8, 8)

        # Labels
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Segoe UI", 10))

        painter.drawText(QRect(0, 0, 80, 40), Qt.AlignmentFlag.AlignCenter, "Classic")
        painter.drawText(QRect(80, 0, 80, 40), Qt.AlignmentFlag.AlignCenter, "Meltdown")
        painter.drawText(QRect(160, 0, 80, 40), Qt.AlignmentFlag.AlignCenter, "Halloween")

        # Sliding knob
        painter.setBrush(QColor(80, 80, 80))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self._knob_x, 0, 80, 40, 8, 8)
