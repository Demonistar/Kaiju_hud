# core/theme_manager.py

from PyQt6.QtCore import QObject, pyqtSignal
from core.app_state import AppState


class ThemeManager(QObject):
    """
    Generates QSS stylesheets based on:
      - Theme (Classic / Meltdown / Halloween)
      - Glow level (Subtle / Medium / Maximum)

    Emits stylesheet_ready(str) when a new stylesheet is generated.
    MainWindow listens and applies it.

    Pure logic. No UI code.
    """

    stylesheet_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.app_state = AppState.instance()

        # Connect to global state changes
        self.app_state.theme_changed.connect(self._on_theme_changed)
        self.app_state.glow_changed.connect(self._on_glow_changed)

        # Initial stylesheet
        self._emit_stylesheet()

    # ---------------------------------------------------------
    # SIGNAL HANDLERS
    # ---------------------------------------------------------

    def _on_theme_changed(self, _):
        self._emit_stylesheet()

    def _on_glow_changed(self, _):
        self._emit_stylesheet()

    # ---------------------------------------------------------
    # INTERNAL: BUILD STYLESHEET
    # ---------------------------------------------------------

    def _emit_stylesheet(self):
        theme = self.app_state.theme()
        glow = self.app_state.glow()

        qss = self._build_stylesheet(theme, glow)
        self.stylesheet_ready.emit(qss)

    # ---------------------------------------------------------
    # THEME + GLOW → QSS
    # ---------------------------------------------------------

    def _build_stylesheet(self, theme: str, glow: str) -> str:
        """
        Returns a complete QSS string for the current theme + glow level.
        """

        # -------------------------------
        # Color palettes
        # -------------------------------
        palettes = {
            "classic": {
                "primary": "#00F6FF",
                "background": "#001F3F",
                "accent": "#00FFC8"
            },
            "meltdown": {
                "primary": "#FF2400",
                "background": "#0A0000",
                "accent": "#FF6A00"
            },
            "halloween": {
                "primary": "#39FF14",
                "background": "#000000",
                "accent": "#FF7A00"
            }
        }

        colors = palettes.get(theme, palettes["classic"])

        # -------------------------------
        # Glow blur radius
        # -------------------------------
        glow_map = {
            "subtle": 4,
            "medium": 8,
            "maximum": 16
        }

        blur = glow_map.get(glow, 4)

        # -------------------------------
        # Build QSS
        # -------------------------------
        qss = f"""
        QWidget {{
            background-color: {colors['background']};
            color: {colors['primary']};
            font-family: 'Segoe UI', sans-serif;
        }}

        QPushButton {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px 12px;
            border-radius: 4px;
        }}

        QPushButton:hover {{
            border-color: {colors['accent']};
            color: {colors['accent']};
        }}

        QLineEdit {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px;
            border-radius: 4px;
        }}

        QTextEdit {{
            background-color: {colors['background']};
            border: 1px solid {colors['primary']};
            padding: 6px;
            border-radius: 4px;
        }}

        /* Glow hint (used by widgets that apply QGraphicsDropShadowEffect) */
        *[glow='true'] {{
            qproperty-blurRadius: {blur};
            qproperty-glowColor: {colors['primary']};
        }}
        """

        return qss.strip()
