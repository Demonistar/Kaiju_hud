# main.py

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout

from core.dispatcher import Dispatcher
from core.column_manager import ColumnManager
from core.glow_manager import GlowManager
from core.app_state import AppState
from core.theme_manager import ThemeManager
from core.settings_manager import SettingsManager
from storage.database import Database

from providers.claude_provider import ClaudeProvider
from providers.chatgpt_provider import ChatGPTProvider
from providers.grok_provider import GrokProvider
from providers.copilot_browser_provider import CopilotBrowserProvider
from local_llm.ollama_client import OllamaClient

from ui.prompt.prompt_bar import PromptBar
from ui.prompt.target_selector import TargetSelector

from ui.panels.top.claude_top import ClaudeTop
from ui.panels.bottom.claude_chat import ClaudeChat

from ui.panels.top.chatgpt_top import ChatGPTTop
from ui.panels.bottom.chatgpt_chat import ChatGPTChat

from ui.panels.top.grok_top import GrokTop
from ui.panels.bottom.grok_chat import GrokChat

from ui.panels.top.copilot_top import CopilotTop
from ui.panels.bottom.copilot_chat import CopilotChat

from ui.panels.top.local_top import LocalTop
from ui.panels.bottom.local_chat import LocalChat


class DeckHUD(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kaiju Command Bridge")
        self.resize(1600, 900)

        GlowManager()

        # -------------------------
        # SETTINGS + THEME + STATE
        # -------------------------
        self.settings = SettingsManager()

        self.theme_manager = ThemeManager()
        self.theme_manager.stylesheet_ready.connect(self.apply_stylesheet)

        app_state = AppState.instance()
        app_state.set_theme(self.settings.get_last_theme())
        app_state.set_glow(self.settings.get_last_glow())
        app_state.set_window_mode(self.settings.get_last_window_mode())

        # -------------------------
        # DATABASE + DISPATCHER
        # -------------------------
        self.db = Database()
        self.dispatcher = Dispatcher(db_client=self.db)

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout()
        central.setLayout(root)

        # -------------------------
        # TOP ROW
        # -------------------------
        top_row = QHBoxLayout()

        self.claude_top = ClaudeTop()
        self.chatgpt_top = ChatGPTTop()
        self.grok_top = GrokTop()
        self.copilot_top = CopilotTop()
        self.local_top = LocalTop()

        top_row.addWidget(self.claude_top)
        top_row.addWidget(self.chatgpt_top)
        top_row.addWidget(self.grok_top)
        top_row.addWidget(self.copilot_top)
        top_row.addWidget(self.local_top)

        root.addLayout(top_row)

        # -------------------------
        # BOTTOM ROW
        # -------------------------
        bottom_row = QHBoxLayout()

        self.claude_chat = ClaudeChat(self.dispatcher)
        self.chatgpt_chat = ChatGPTChat(self.dispatcher)
        self.grok_chat = GrokChat(self.dispatcher)
        self.copilot_chat = CopilotChat(self.dispatcher)
        self.local_chat = LocalChat(self.dispatcher)

        bottom_row.addWidget(self.claude_chat)
        bottom_row.addWidget(self.chatgpt_chat)
        bottom_row.addWidget(self.grok_chat)
        bottom_row.addWidget(self.copilot_chat)
        bottom_row.addWidget(self.local_chat)

        root.addLayout(bottom_row)

        # -------------------------
        # TARGET SELECTOR + PROMPT
        # -------------------------
        self.target_selector = TargetSelector()
        root.addWidget(self.target_selector)

        self.prompt_bar = PromptBar(self.dispatcher)
        root.addWidget(self.prompt_bar)

        self.target_selector.targets_changed.connect(self.prompt_bar.set_targets)

        # -------------------------
        # COLUMN MANAGER
        # -------------------------
        cm = ColumnManager.instance()
        cm.register("claude", self.claude_top, self.claude_chat)
        cm.register("chatgpt", self.chatgpt_top, self.chatgpt_chat)
        cm.register("grok", self.grok_top, self.grok_chat)
        cm.register("copilot", self.copilot_top, self.copilot_chat)
        cm.register("local", self.local_top, self.local_chat)

        # -------------------------
        # PROVIDERS + API KEYS
        # -------------------------
        claude_key = self.settings.get_api_key("claude")
        chatgpt_key = self.settings.get_api_key("chatgpt")
        grok_key = self.settings.get_api_key("grok")
        local_model = self.settings.get_api_key("local_model")

        self.claude_provider = ClaudeProvider(api_key=claude_key)
        self.chatgpt_provider = ChatGPTProvider(api_key=chatgpt_key)
        self.grok_provider = GrokProvider(api_key=grok_key)
        self.copilot_provider = CopilotBrowserProvider()

        self.local_provider = OllamaClient()
        self.local_provider.set_model(local_model or "dolphin-mistral")

        self.claude_provider.bind(self.dispatcher)
        self.chatgpt_provider.bind(self.dispatcher)
        self.grok_provider.bind(self.dispatcher)
        self.copilot_provider.bind(self.dispatcher)
        self.local_provider.bind(self.dispatcher)

        self.dispatcher.register_provider("claude", self.claude_provider.provider_handler)
        self.dispatcher.register_provider("chatgpt", self.chatgpt_provider.provider_handler)
        self.dispatcher.register_provider("grok", self.grok_provider.provider_handler)
        self.dispatcher.register_provider("copilot", self.copilot_provider.provider_handler)
        self.dispatcher.register_provider("local", self.local_provider.provider_handler)

    # -------------------------
    # APPLY STYLESHEET
    # -------------------------
    def apply_stylesheet(self, css: str):
        QApplication.instance().setStyleSheet(css)


def main():
    app = QApplication(sys.argv)

    window = DeckHUD()
    window.show()

    if hasattr(window, "copilot_provider"):
        app.aboutToQuit.connect(window.copilot_provider.shutdown)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()