# core/column_manager.py

from PyQt6.QtCore import QObject, pyqtSignal


class ColumnManager(QObject):
    """
    Manages which AI columns are visible and how much horizontal
    space each active column should occupy.

    This is a pure logic layer:
      - No UI code
      - No widget references
      - No theme logic
      - No provider logic

    The UI listens to layout_changed and adjusts itself.
    """

    # Singleton instance
    _instance = None

    @staticmethod
    def instance():
        if ColumnManager._instance is None:
            ColumnManager._instance = ColumnManager()
        return ColumnManager._instance

    # Emitted whenever the active column set changes
    # Dict: { 'claude': True/False, ... }
    columns_changed = pyqtSignal(dict)

    # Emitted whenever widths must be recalculated
    # Dict: { 'claude': 0.25, 'chatgpt': 0.25, ... }
    layout_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initial state: all columns visible
        self.columns = {
            "claude": True,
            "chatgpt": True,
            "grok": True,
            "copilot": True,
            "local": True
        }

        # Cached widths
        self.widths = {}

        # Registered widgets (top + bottom pairs)
        self._widgets = {}   # name -> (top_widget, bottom_widget)

        # Compute initial layout
        self._recalculate_layout()

    # ---------------------------------------------------------
    # REGISTRATION
    # ---------------------------------------------------------

    def register(self, name: str, top_widget, bottom_widget):
        """Register UI widgets so ColumnManager can show/hide them."""
        self._widgets[name] = (top_widget, bottom_widget)

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def toggle(self, name: str):
        """Collapse or expand a column."""
        if name not in self.columns:
            return

        self.columns[name] = not self.columns[name]
        self.columns_changed.emit(self.columns.copy())
        self._recalculate_layout()

    def set_visible(self, name: str, visible: bool):
        """Explicitly set a column's visibility."""
        if name not in self.columns:
            return

        self.columns[name] = visible
        self.columns_changed.emit(self.columns.copy())
        self._recalculate_layout()

    def hide_all(self):
        """Collapse all columns."""
        for k in self.columns:
            self.columns[k] = False
        self.columns_changed.emit(self.columns.copy())
        self._recalculate_layout()

    def show_all(self):
        """Expand all columns."""
        for k in self.columns:
            self.columns[k] = True
        self.columns_changed.emit(self.columns.copy())
        self._recalculate_layout()

    def get_widths(self) -> dict:
        """Return the current width distribution."""
        return self.widths.copy()

    # ---------------------------------------------------------
    # INTERNAL LAYOUT LOGIC
    # ---------------------------------------------------------

    def _recalculate_layout(self):
        """
        Compute width percentages for all active columns.
        If none are active, emit empty dict (UI will show placeholder).
        Also show/hide registered widgets accordingly.
        """
        active = [name for name, visible in self.columns.items() if visible]
        count = len(active)

        if count == 0:
            # No columns active → placeholder mode
            self.widths = {}
            self.layout_changed.emit({})

            # Hide all registered widgets
            for name, pair in self._widgets.items():
                top, bottom = pair
                top.hide()
                bottom.hide()

            return

        width = 1.0 / count

        new_widths = {}
        for name in self.columns:
            new_widths[name] = width if self.columns[name] else 0.0

        self.widths = new_widths
        self.layout_changed.emit(new_widths.copy())

        # Show/hide widgets based on visibility
        for name, pair in self._widgets.items():
            top, bottom = pair
            if self.columns.get(name, False):
                top.show()
                bottom.show()
            else:
                top.hide()
                bottom.hide()

    # ---------------------------------------------------------
    # PROGRAMMATIC CONTROL (Phase 2‑ready)
    # ---------------------------------------------------------

    def active_columns(self):
        """Return a list of currently visible columns."""
        return [k for k, v in self.columns.items() if v]

    def is_active(self, name: str) -> bool:
        """Check if a column is visible."""
        return self.columns.get(name, False)
