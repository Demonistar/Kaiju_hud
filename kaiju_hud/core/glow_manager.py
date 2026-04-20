# core/glow_manager.py

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from core.app_state import AppState


class GlowManager(QObject):
    """
    Centralized glow controller.
    Widgets register themselves and receive updated QGraphicsDropShadowEffect
    objects whenever theme or glow level changes.

    Pure logic layer:
      - No stylesheet manipulation (ThemeManager handles that)
      - No widget creation (widgets register themselves)
      - No UI coupling
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.app_state = AppState.instance()

        # Registered widgets: { widget: intensity }
        self._widgets = {}

        # Connect to global state
        self.app_state.theme_changed.connect(self._update_all)
        self.app_state.glow_changed.connect(self._update_all)

        # Initial update
        self._update_all()

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def register_widget(self, widget, intensity: str = "medium"):
        """
        Register a widget to receive glow updates.
        intensity: 'subtle', 'medium', 'maximum'
        """
        self._widgets[widget] = intensity
        self._apply_glow(widget, intensity)

    # ---------------------------------------------------------
    # INTERNAL: UPDATE ALL WIDGETS
    # ---------------------------------------------------------

    def _update_all(self, *_):
        """Reapply glow to all registered widgets."""
        for widget, intensity in self._widgets.items():
            self._apply_glow(widget, intensity)

    # ---------------------------------------------------------
    # INTERNAL: APPLY GLOW TO ONE WIDGET
    # ---------------------------------------------------------

    def _apply_glow(self, widget, intensity: str):
        """
        Create and apply a QGraphicsDropShadowEffect based on:
          - current theme primary color
          - glow intensity (blur radius)
        """

        # Theme → primary color
        theme = self.app_state.theme()
        primary_color = self._theme_primary_color(theme)

        # Glow → blur radius
        blur_radius = self._glow_blur(intensity)

        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur_radius)
        effect.setColor(primary_color)
        effect.setOffset(0, 0)

        widget.setGraphicsEffect(effect)

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def _theme_primary_color(self, theme: str):
        """Return QColor for the theme's primary color."""
        from PyQt6.QtGui import QColor

        palettes = {
            "classic": "#00F6FF",
            "meltdown": "#FF2400",
            "halloween": "#39FF14"
        }

        return QColor(palettes.get(theme, "#00F6FF"))

    def _glow_blur(self, intensity: str) -> int:
        """Return blur radius for glow intensity."""
        mapping = {
            "subtle": 4,
            "medium": 8,
            "maximum": 16
        }
        return mapping.get(intensity.lower(), 8)
