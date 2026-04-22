from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from storage.database import DB_PATH


class DBViewDialog(QDialog):
    _visible_columns = [
        "key_id",
        "timestamp_est",
        "session_id",
        "user_prompt",
        "bobby_response",
        "bobby_lesson",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session DB Inspector")
        self.resize(1300, 760)

        self._rows: list[dict] = []
        self._build_ui()
        self.refresh_rows()

    def _build_ui(self):
        root = QVBoxLayout(self)

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(6)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest first", "Oldest first"])

        self.session_filter = QLineEdit()
        self.session_filter.setPlaceholderText("Filter by session_id")

        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Search user_prompt or bobby_lesson")

        self.refresh_btn = QPushButton("Refresh")
        self.export_visible_btn = QPushButton("Export Visible CSV")
        self.export_full_btn = QPushButton("Export Full Table CSV")

        controls.addWidget(QLabel("Sort"), 0, 0)
        controls.addWidget(self.sort_combo, 0, 1)
        controls.addWidget(QLabel("Session"), 0, 2)
        controls.addWidget(self.session_filter, 0, 3)
        controls.addWidget(QLabel("Search"), 0, 4)
        controls.addWidget(self.search_filter, 0, 5)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.refresh_btn)
        buttons_row.addWidget(self.export_visible_btn)
        buttons_row.addWidget(self.export_full_btn)
        buttons_row.addStretch(1)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._visible_columns))
        self.table.setHorizontalHeaderLabels(self._visible_columns)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        self.detail_pane = QPlainTextEdit()
        self.detail_pane.setReadOnly(True)
        self.detail_pane.setPlaceholderText("Select a row to inspect full field contents.")

        root.addLayout(controls)
        root.addLayout(buttons_row)
        root.addWidget(self.table, 1)
        root.addWidget(QLabel("Row details"))
        root.addWidget(self.detail_pane, 1)

        self.sort_combo.currentIndexChanged.connect(self.refresh_rows)
        self.session_filter.returnPressed.connect(self.refresh_rows)
        self.search_filter.returnPressed.connect(self.refresh_rows)
        self.refresh_btn.clicked.connect(self.refresh_rows)
        self.export_visible_btn.clicked.connect(self.export_visible_csv)
        self.export_full_btn.clicked.connect(self.export_full_csv)
        self.table.itemSelectionChanged.connect(self._update_details)

    def refresh_rows(self):
        order = "DESC" if self.sort_combo.currentIndex() == 0 else "ASC"
        session_id = self.session_filter.text().strip()
        search_text = self.search_filter.text().strip()
        self._rows = self._query_rows(order=order, session_id=session_id, search_text=search_text)
        self._populate_table(self._rows)

    def _query_rows(self, order: str, session_id: str = "", search_text: str = "") -> list[dict]:
        query = """
            SELECT *
            FROM full_sessions
            WHERE (? = '' OR session_id LIKE ?)
              AND (
                    ? = ''
                    OR user_prompt LIKE ?
                    OR bobby_lesson LIKE ?
                  )
            ORDER BY key_id {}
        """.format(order)

        session_like = f"%{session_id}%"
        text_like = f"%{search_text}%"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                query,
                (session_id, session_like, search_text, text_like, text_like),
            )
            return [dict(row) for row in cur.fetchall()]

    def _populate_table(self, rows: list[dict]):
        self.table.clearContents()
        self.table.setRowCount(len(rows))

        for row_idx, row in enumerate(rows):
            for col_idx, col_name in enumerate(self._visible_columns):
                value = row.get(col_name)
                display = self._truncate(value)
                item = QTableWidgetItem(display)
                if col_name == "key_id":
                    item.setData(Qt.ItemDataRole.UserRole, row.get("key_id"))
                self.table.setItem(row_idx, col_idx, item)

        if rows:
            self.table.selectRow(0)
        else:
            self.detail_pane.clear()

    def _update_details(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            self.detail_pane.clear()
            return

        row_idx = selected[0].row()
        if row_idx < 0 or row_idx >= len(self._rows):
            self.detail_pane.clear()
            return

        row = self._rows[row_idx]
        lines = [f"{key}: {row.get(key)}" for key in row.keys()]
        self.detail_pane.setPlainText("\n".join(lines))

    def export_visible_csv(self):
        self._export_rows_to_csv(self._rows)

    def export_full_csv(self):
        full_rows = self._query_rows(order="DESC")
        self._export_rows_to_csv(full_rows)

    def _export_rows_to_csv(self, rows: list[dict]):
        if not rows:
            QMessageBox.information(self, "No data", "No rows available to export.")
            return

        default_path = str(Path.home() / "full_sessions_export.csv")
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save full_sessions CSV",
            default_path,
            "CSV Files (*.csv)",
        )
        if not target_path:
            return

        headers = list(rows[0].keys())
        with open(target_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        QMessageBox.information(self, "Export complete", f"CSV saved to:\n{target_path}")

    @staticmethod
    def _truncate(value, limit: int = 80) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) <= limit:
            return text
        return f"{text[:limit - 3]}..."
