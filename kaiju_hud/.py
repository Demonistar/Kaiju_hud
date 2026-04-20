# main.py

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout

from core.dispatcher import Dispatcher
from core.column_manager import ColumnManager
from core.glow_manager import GlowManager
from core.app_state import AppState

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

        self.setWindowTitle("Deck HUD")
        self.resize(1600, 900)

        GlowManager()  # global glow system
        AppState.instance()  # global theme + state

        self.dispatcher = Dispatcher()

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout()
        central.setLayout(root)

        # -------------------------
        # TOP ROW (5 AI TOP PANELS)
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

        # ----------------------------
        # BOTTOM ROW (5 AI CHAT PANELS)
        # ----------------------------
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

        # -------------------------
        # COLUMN MANAGER REGISTRATION
        # -------------------------
        cm = ColumnManager.instance()
        cm.register("claude", self.claude_top, self.claude_chat)
        cm.register("chatgpt", self.chatgpt_top, self.chatgpt_chat)
        cm.register("grok", self.grok_top, self.grok_chat)
        cm.register("copilot", self.copilot_top, self.copilot_chat)
        cm.register("local", self.local_top, self.local_chat)


def main():
    app = QApplication(sys.argv)
    window = DeckHUD()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
