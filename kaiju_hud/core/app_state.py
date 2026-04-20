# core/app_state.py

from PyQt6.QtCore import QObject, pyqtSignal


class AppState(QObject):
    """
    Global application state container.
    Pure state storage + signals.
    No logic, no UI code, no layout math.

    Other managers read/write this state.
    """

    # ---------------------------------------------------------
    # SIGNALS
    # ---------------------------------------------------------

    theme_changed = pyqtSignal(str)          # 'classic', 'meltdown', 'halloween', etc.
    glow_changed = pyqtSignal(str)           # 'subtle', 'medium', 'maximum'
    window_mode_changed = pyqtSignal(str)    # 'FS', 'BL', 'WI'
    columns_changed = pyqtSignal(dict)       # { 'claude': True/False, ... }

    # ---------------------------------------------------------
    # SINGLETON IMPLEMENTATION
    # ---------------------------------------------------------

    _instance = None

    @staticmethod
    def instance():
        if AppState._instance is None:
            AppState._instance = AppState()
        return AppState._instance

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------

    def __init__(self):
        super().__init__()

        # Default values
        self._theme = "classic"
        self._glow = "subtle"
        self._window_mode = "WI"  # Windowed by default

        # Mirrors ColumnManager but at global state level
        self._columns = {
            "claude": True,
            "chatgpt": True,
            "grok": True,
            "copilot": True,
            "local": True
        }

    # ---------------------------------------------------------
    # THEME
    # ---------------------------------------------------------

    def theme(self) -> str:
        return self._theme

    def set_theme(self, value: str):
        if value != self._theme:
            self._theme = value
            self.theme_changed.emit(value)

    # ---------------------------------------------------------
    # GLOW LEVEL
    # ---------------------------------------------------------

    def glow(self) -> str:
        return self._glow

    def set_glow(self, value: str):
        if value != self._glow:
            self._glow = value
            self.glow_changed.emit(value)

    # ---------------------------------------------------------
    # WINDOW MODE (FS / BL / WI)
    # ---------------------------------------------------------

    def window_mode(self) -> str:
        return self._window_mode

    def set_window_mode(self, value: str):
        if value != self._window_mode:
            self._window_mode = value
            self.window_mode_changed.emit(value)

    # ---------------------------------------------------------
    # COLUMNS
    # ---------------------------------------------------------

    def columns(self) -> dict:
        return self._columns.copy()

    def set_columns(self, new_columns: dict):
        """
        Replace entire column visibility dict.
        ColumnManager will call this.
        """
        self._columns = new_columns.copy()
        self.columns_changed.emit(new_columns.copy())

    def set_column_visible(self, name: str, visible: bool):
        """
        Update a single column's visibility.
        """
        if name in self._columns and self._columns[name] != visible:
            self._columns[name] = visible
            self.columns_changed.emit(self._columns.copy())
