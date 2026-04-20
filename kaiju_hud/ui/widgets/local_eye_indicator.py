# ui/widgets/local_eye_indicator.py

import os
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QWidget

from core.app_state import AppState
from core.glow_manager import GlowManager


class LocalEyeIndicator(QWidget):
    """
    The pulsing Kaiju eye widget.
    - Observer mode: open eye + pulsing opacity
    - Active mode: closed eye, no pulse
    - Registers with GlowManager for theme-aware glow
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(64, 64)
        self._opacity = 1.0
        self._observer_mode = True

        # Load images or fallback
        self.eye_open = self._load_image("assets/eye_open.png")
        self.eye_closed = self._load_image("assets/eye_closed.png")

        # Animation
        self.anim = QPropertyAnimation(self, b"opacity")
        self.anim.setDuration(2000)
        self.anim.setStartValue(0.6)
        self.anim.setEndValue(1.0)
        self.anim.setLoopCount(-1)

        # Glow manager registration
        GlowManager().register_widget(self, intensity="medium")

        # Theme updates
        AppState.instance().theme_changed.connect(self.update)

        # Start in observer mode
        self.set_observer_mode(True)

    # ---------------------------------------------------------
    # IMAGE LOADING
    # ---------------------------------------------------------

    def _load_image(self, path):
        if os.path.exists(path):
            return QPixmap(path)
        return None  # triggers placeholder mode

    # ---------------------------------------------------------
    # OPACITY PROPERTY (ANIMATABLE)
    # ---------------------------------------------------------

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.update()

    opacity = pyqtProperty(float, fget=get_opacity, fset=set_opacity)

    # ---------------------------------------------------------
    # MODE SWITCH
    # ---------------------------------------------------------

    def set_observer_mode(self, enabled: bool):
        """True = open eye + pulse, False = closed eye + static."""
        self._observer_mode = enabled

        if enabled:
            self.anim.start()
        else:
            self.anim.stop()
            self._opacity = 1.0
            self.update()

    # ---------------------------------------------------------
    # PAINT EVENT
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.setOpacity(self._opacity)

        if self._observer_mode:
            if self.eye_open:
                painter.drawPixmap(0, 0, 64, 64, self.eye_open)
            else:
                self._draw_placeholder(painter, QColor("#00F6FF"))
        else:
            if self.eye_closed:
                painter.drawPixmap(0, 0, 64, 64, self.eye_closed)
            else:
                self._draw_placeholder(painter, QColor("#555555"))

    # ---------------------------------------------------------
    # PLACEHOLDER DRAWING
    # ---------------------------------------------------------

    def _draw_placeholder(self, painter, color):
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
