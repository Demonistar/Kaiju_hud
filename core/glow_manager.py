# core/glow_manager.py

from PyQt6.QtCore import QObject
from core.app_state import AppState


class GlowManager(QObject):
    """
    Centralized glow controller.
    Widgets register themselves and receive updated border‑based glow
    whenever theme or glow level changes.
    """

    _instance = None

    @staticmethod
    def instance():
        if GlowManager._instance is None:
            GlowManager._instance = GlowManager()
        return GlowManager._instance

    def __init__(self, parent=None):
        super().__init__(parent)

        GlowManager._instance = self

        self.app_state = AppState.instance()

        # Lazy import to avoid circular import with ThemeManager
        from core.theme_manager import ThemeManager
        self.theme_manager = ThemeManager.instance()

        # Registered widgets: { widget: intensity }
        self._widgets = {}

        # Listen to theme + glow changes
        self.app_state.theme_changed.connect(self._update_all)
        self.app_state.glow_changed.connect(self._update_all)
        self.theme_manager.palette_changed.connect(self._update_all)

        # Initial update
        self._update_all()

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def register_widget(self, widget, intensity: str = "medium"):
        """Register a widget to receive glow updates."""
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
    # INTERNAL: APPLY GLOW TO ONE WIDGET  (BORDER‑BASED)
    # ---------------------------------------------------------

    def _apply_glow(self, widget, intensity: str):
        pass
