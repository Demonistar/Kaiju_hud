# core/theme_manager.py

from PyQt6.QtCore import QObject, pyqtSignal
from core.app_state import AppState


class ThemeManager(QObject):
    """
    Generates QSS stylesheets AND exposes theme palettes for custom widgets.
    Emits:
      - stylesheet_ready(str)
      - palette_changed(dict)
    """

    stylesheet_ready = pyqtSignal(str)
    palette_changed = pyqtSignal(dict)

    _instance = None

    @staticmethod
    def instance():
        if ThemeManager._instance is None:
            ThemeManager._instance = ThemeManager()
        return ThemeManager._instance

    # ---------------------------------------------------------
    # PALETTES (GLOBAL)
    # ---------------------------------------------------------
    PALETTES = {
        "classic": {
            "primary": "#00F6FF",
            "background": "#001F3F",
            "accent": "#00FFC8",
            "text": "#FFFFFF"
        },
        "meltdown": {
            "primary": "#FF2400",
            "background": "#0A0000",
            "accent": "#FF6A00",
            "text": "#FFFFFF"
        },
        "halloween": {
            "primary": "#39FF14",
            "background": "#000000",
            "accent": "#FF7A00",
            "text": "#FFFFFF"
        }
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        ThemeManager._instance = self

        self.app_state = AppState.instance()

        # Connect to global state changes
        self.app_state.theme_changed.connect(self._on_theme_changed)
        self.app_state.glow_changed.connect(self._on_glow_changed)

        # Cache current palette
        self._palette = self._compute_palette()

        # Initial stylesheet + palette
        self._emit_stylesheet()
        self.palette_changed.emit(self._palette)

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def palette(self) -> dict:
        """Return the current theme palette."""
        return self._palette.copy()

    # ---------------------------------------------------------
    # SIGNAL HANDLERS
    # ---------------------------------------------------------

    def _on_theme_changed(self, _):
        self._palette = self._compute_palette()
        self.palette_changed.emit(self._palette)
        self._emit_stylesheet()

    def _on_glow_changed(self, _):
        self._emit_stylesheet()

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    def _compute_palette(self) -> dict:
        theme = self.app_state.theme()
        return ThemeManager.PALETTES.get(theme, ThemeManager.PALETTES["classic"])

    def _emit_stylesheet(self):
        theme = self.app_state.theme()
        glow = self.app_state.glow()

        qss = self._build_stylesheet(theme, glow)
        self.stylesheet_ready.emit(qss)

    # ---------------------------------------------------------
    # THEME + GLOW → QSS
    # ---------------------------------------------------------

    def _build_stylesheet(self, theme: str, glow: str) -> str:
        colors = ThemeManager.PALETTES.get(theme, ThemeManager.PALETTES["classic"])

        glow_map = {
            "subtle": 4,
            "medium": 8,
            "maximum": 16
        }

        blur = glow_map.get(glow, 4)

        qss = f"""
        QWidget {{
            background-color: {colors['background']};
            color: {colors['text']};
            font-family: 'Segoe UI', sans-serif;
        }}

        QPushButton {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px 12px;
            border-radius: 6px;
            color: {colors['accent']};
        }}

        QPushButton:hover {{
            border-color: {colors['accent']};
            color: {colors['primary']};
        }}

        QLineEdit {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px;
            border-radius: 4px;
            color: {colors['text']};
        }}

        QTextEdit {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px;
            border-radius: 4px;
            color: {colors['text']};
        }}


        """

        return qss.strip()
