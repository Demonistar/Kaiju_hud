# ui/prompt/prompt_bar.py

import os
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QFont, QTextOption
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QPushButton, QHBoxLayout, QVBoxLayout, QSizePolicy
)

from core.glow_manager import GlowManager
from core.app_state import AppState
from core.settings_manager import SettingsManager
from ui.prompt.hidden_prompt_manager import HiddenPromptManagerDialog


class PromptBar(QWidget):
    """
    Full-width floating prompt bar at the bottom of the HUD.
    """

    message_sent = pyqtSignal(list, str)

    def __init__(self, dispatcher, parent=None):
        super().__init__(parent)

        self.dispatcher = dispatcher
        self.targets = []
        self._resizing = False  # <-- prevents recursive resize loops

        self._settings = SettingsManager()
        self._hidden_prompt_dialog = None
        self._hidden_prompt_enabled = self._settings.get_hidden_prompt_enabled()
        self._hidden_prompt_profile = self._settings.get_hidden_prompt_profile()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(140)

        GlowManager().register_widget(self, intensity="maximum")
        AppState.instance().theme_changed.connect(self.update)

        # -----------------------------------------------------
        # TEXT INPUT
        # -----------------------------------------------------
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Segoe UI", 11))
        self.text_edit.setPlaceholderText("Type your prompt...")
        self.text_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.text_edit.textChanged.connect(self._schedule_resize)
        self.text_edit.installEventFilter(self)

        # -----------------------------------------------------
        # SEND BUTTON
        # -----------------------------------------------------
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(40)
        self.send_btn.clicked.connect(self._on_send)
        GlowManager().register_widget(self.send_btn, intensity="medium")

        # -----------------------------------------------------
        # HIDDEN PROMPT BUTTON
        # -----------------------------------------------------
        self.hidden_prompt_btn = QPushButton()
        self.hidden_prompt_btn.setFixedHeight(self.send_btn.height())
        self.hidden_prompt_btn.clicked.connect(self._open_hidden_prompt_manager)
        GlowManager().register_widget(self.hidden_prompt_btn, intensity="medium")
        self._refresh_hidden_prompt_button()

        # -----------------------------------------------------
        # LAYOUT
        # -----------------------------------------------------
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.hidden_prompt_btn)
        row.addWidget(self.send_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        layout.addLayout(row)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

    # ---------------------------------------------------------
    # TARGETS
    # ---------------------------------------------------------

    def set_targets(self, targets: list):
        self.targets = targets

    # ---------------------------------------------------------
    # SAFE AUTO-RESIZE
    # ---------------------------------------------------------

    def _schedule_resize(self):
        """Defer resize to break recursive layout loops."""
        if self._resizing:
            return
        QTimer.singleShot(0, self._auto_resize)

    def _auto_resize(self):
        if self._resizing:
            return

        self._resizing = True

        doc_height = self.text_edit.document().size().height()
        max_height = 120
        new_height = int(min(max(40, doc_height + 10), max_height))

        self.text_edit.setFixedHeight(new_height)

        self._resizing = False

    # ---------------------------------------------------------
    # KEY HANDLING
    # ---------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self.text_edit:
            if event.type() == event.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        return False
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    # ---------------------------------------------------------
    # HIDDEN PROMPT MANAGER
    # ---------------------------------------------------------

    def _open_hidden_prompt_manager(self):
        if self._hidden_prompt_dialog is None:
            self._hidden_prompt_dialog = HiddenPromptManagerDialog(self)
            self._hidden_prompt_dialog.settings_changed.connect(self._on_hidden_prompt_settings_changed)

        self._hidden_prompt_dialog.refresh_from_storage()
        self._hidden_prompt_dialog.show()
        self._hidden_prompt_dialog.raise_()
        self._hidden_prompt_dialog.activateWindow()

    def _on_hidden_prompt_settings_changed(self, enabled: bool, profile: str):
        self._hidden_prompt_enabled = enabled
        self._hidden_prompt_profile = profile
        self._refresh_hidden_prompt_button()

    def _refresh_hidden_prompt_button(self):
        profile_name = (self._hidden_prompt_profile or "None").strip() or "None"
        on_off = "ON" if self._hidden_prompt_enabled else "OFF"
        self.hidden_prompt_btn.setText(f"Hidden: {on_off} : {profile_name}")

        if self._hidden_prompt_enabled:
            self.hidden_prompt_btn.setStyleSheet(
                "QPushButton { background-color: #1f7a3f; color: white; font-weight: 600; padding: 0 14px; }"
            )
        else:
            self.hidden_prompt_btn.setStyleSheet("")

    # ---------------------------------------------------------
    # SEND HANDLER
    # ---------------------------------------------------------

    def _on_send(self):
        content = self.text_edit.toPlainText().strip()
        if not content or not self.targets:
            return

        self._play_roar()

        self._hidden_prompt_enabled = self._settings.get_hidden_prompt_enabled()
        self._hidden_prompt_profile = self._settings.get_hidden_prompt_profile()
        hidden_suffix = self._settings.get_hidden_prompt_text(self._hidden_prompt_profile)

        provider_content = content
        if self._hidden_prompt_enabled and hidden_suffix.strip():
            provider_content = f"{content}\n\n{hidden_suffix.strip()}"

        self.dispatcher.send_message(
            self.targets,
            display_content=content,
            provider_content=provider_content,
        )
        self.message_sent.emit(self.targets, content)

        self.text_edit.clear()
        self._refresh_hidden_prompt_button()

    # ---------------------------------------------------------
    # ROAR SOUND
    # ---------------------------------------------------------

    def _play_roar(self):
        path = "assets/roar.wav"
        if not os.path.exists(path):
            return

        try:
            from PyQt6.QtMultimedia import QSoundEffect
            self.roar = QSoundEffect()
            self.roar.setSource(QUrl.fromLocalFile(path))
            self.roar.setVolume(0.25)
            self.roar.play()
        except Exception:
            pass
