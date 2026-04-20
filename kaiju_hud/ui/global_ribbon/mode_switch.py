# ui/global_ribbon/mode_switch.py

from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtSignal, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from core.app_state import AppState
from core.glow_manager import GlowManager


class ModeSwitch(QWidget):
    """
    Three‑state sliding switch for window mode:
      FS = Fullscreen
      BL = Borderless
      WI = Windowed

    Pure UI widget:
      - Emits mode_changed(str)
      - Updates AppState.window_mode
      - Animated sliding knob
    """

    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(180, 40)

        self.app_state = AppState.instance()
        self.current_mode = self.app_state.window_mode()  # FS / BL / WI

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
    # MODE CHANGE
    # ---------------------------------------------------------

    def set_mode(self, mode: str):
        if mode not in ("FS", "BL", "WI"):
            return

        self.current_mode = mode
        self.app_state.set_window_mode(mode)
        self.mode_changed.emit(mode)
        self._update_knob_position()

    # ---------------------------------------------------------
    # INTERNAL: KNOB POSITION
    # ---------------------------------------------------------

    def _update_knob_position(self, initial=False):
        positions = {
            "FS": 0,
            "BL": 60,
            "WI": 120
        }

        target = positions.get(self.current_mode, 0)

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

        if x < 60:
            self.set_mode("FS")
        elif x < 120:
            self.set_mode("BL")
        else:
            self.set_mode("WI")

    # ---------------------------------------------------------
    # PAINT EVENT
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background bar
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 180, 40, 8, 8)

        # Labels
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Segoe UI", 10))

        painter.drawText(QRect(0, 0, 60, 40), Qt.AlignmentFlag.AlignCenter, "FS")
        painter.drawText(QRect(60, 0, 60, 40), Qt.AlignmentFlag.AlignCenter, "BL")
        painter.drawText(QRect(120, 0, 60, 40), Qt.AlignmentFlag.AlignCenter, "WI")

        # Sliding knob
        painter.setBrush(QColor(80, 80, 80))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self._knob_x, 0, 60, 40, 8, 8)
