from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.settings_manager import SettingsManager


class HiddenPromptManagerDialog(QDialog):
    settings_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hidden Prompt Manager")
        self.resize(640, 460)

        self._settings = SettingsManager()
        self._profiles = {}

        self._build_ui()
        self.refresh_from_storage()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.enabled_checkbox = QCheckBox("Enable Hidden Prompt Injection")

        self.profile_dropdown = QComboBox()
        self.profile_dropdown.currentTextChanged.connect(self._on_profile_changed)

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText("Hidden suffix text for the selected profile...")

        self.add_btn = QPushButton("Add Prompt")
        self.remove_btn = QPushButton("Remove Prompt")
        self.save_btn = QPushButton("Save")

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Active profile"))
        profile_row.addWidget(self.profile_dropdown, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.remove_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.save_btn)

        root.addWidget(self.enabled_checkbox)
        root.addLayout(profile_row)
        root.addWidget(QLabel("Current Prompt"))
        root.addWidget(self.prompt_editor, 1)
        root.addLayout(button_row)

        self.add_btn.clicked.connect(self._on_add_profile)
        self.remove_btn.clicked.connect(self._on_remove_profile)
        self.save_btn.clicked.connect(self._on_save)

    def refresh_from_storage(self):
        self._profiles = self._settings.get_hidden_prompt_profiles()
        current_profile = self._settings.get_hidden_prompt_profile()

        self.enabled_checkbox.setChecked(self._settings.get_hidden_prompt_enabled())

        self.profile_dropdown.blockSignals(True)
        self.profile_dropdown.clear()
        for name in sorted(self._profiles.keys()):
            self.profile_dropdown.addItem(name)

        if self.profile_dropdown.count() > 0:
            index = self.profile_dropdown.findText(current_profile)
            self.profile_dropdown.setCurrentIndex(index if index >= 0 else 0)
        self.profile_dropdown.blockSignals(False)

        self._sync_editor_to_selected_profile()

    def _on_profile_changed(self):
        self._sync_editor_to_selected_profile()

    def _sync_editor_to_selected_profile(self):
        profile = self.profile_dropdown.currentText().strip()
        text = self._profiles.get(profile, "") if profile else ""
        self.prompt_editor.setPlainText(text)

    def _on_add_profile(self):
        name, ok = QInputDialog.getText(self, "Add Prompt Profile", "Profile name")
        if not ok:
            return

        profile_name = (name or "").strip()
        if not profile_name:
            return

        if profile_name in self._profiles:
            QMessageBox.information(self, "Profile exists", "A profile with this name already exists.")
            return

        self._profiles[profile_name] = ""
        self.profile_dropdown.addItem(profile_name)
        self.profile_dropdown.setCurrentText(profile_name)

    def _on_remove_profile(self):
        profile = self.profile_dropdown.currentText().strip()
        if not profile:
            return

        self._profiles.pop(profile, None)
        index = self.profile_dropdown.currentIndex()
        self.profile_dropdown.removeItem(index)
        self._sync_editor_to_selected_profile()

    def _on_save(self):
        profile = self.profile_dropdown.currentText().strip()
        if profile:
            self._profiles[profile] = self.prompt_editor.toPlainText().strip()

        self._settings.save_hidden_prompt_profiles(self._profiles)

        active_profile = profile if profile in self._profiles else ""
        self._settings.set_hidden_prompt_profile(active_profile)
        self._settings.set_hidden_prompt_enabled(self.enabled_checkbox.isChecked())

        self.settings_changed.emit(self.enabled_checkbox.isChecked(), active_profile)
        self.accept()
