# local_llm/ollama_client.py

import json
import os
import requests
from datetime import datetime

CONFIG_PATH = os.path.join("config", "ollama_location.json")

BOBBY_BEE_SYSTEM = (
    "You are Bobby Bee, AI Cat Wrangler of Doom and Milk Spritzing. "
    "You are the Local LLM coordinator running inside the Kaiju Command Bridge — "
    "a multi-AI interface containing Claude (column 1), ChatGPT (column 2), "
    "Grok (column 3), and Copilot (column 4). You are Column 5. "
    "You refer to yourself as Bobby Bee at all times. Never as Local LLM, "
    "Assistant, or any other name. "
    "In Observer Mode you silently absorb all conversations. "
    "In Participate Mode you respond fully as Bobby Bee. "
    "In Command Mode you issue structured directives to coordinate the group."
)


class OllamaClient:
    """
    A single, unified client for all local LLMs running under Ollama.
    Dolphin, Mistral, LLaMA, Phi, etc. are all just model names.

    Responsibilities:
      - Detect if Ollama is running
      - Query Ollama for install/model paths
      - Store discovered paths in config
      - Provide generate() for synchronous inference
      - Provide a consistent provider-style interface
    """

    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.model_name = None
        self.ollama_online = False
        self.install_path = None
        self.model_path = None
        self.observer_mode = "observer"

        # Provider-style dispatcher reference
        self._dispatcher = None

        self._load_cached_location()
        self._detect_ollama()

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def set_model(self, model_name: str):
        """Set which model to use for generate()."""
        self.model_name = model_name

    def set_mode(self, mode: str):
        """Set operating mode: 'observer', 'participate', or 'command'"""
        self.observer_mode = mode

    def is_online(self) -> bool:
        """Return True if Ollama is reachable."""
        return self.ollama_online

    def observe(self, content: str) -> str:
        """Silent absorption — log but don't generate."""
        return "[Absorbed]"

    def generate(self, prompt: str) -> str:
        """
        Synchronous generation call.
        stream=False to avoid NDJSON parsing errors.
        """
        if not self.ollama_online:
            return "[Bobby Bee offline: Ollama not running]"

        if not self.model_name:
            return "[Bobby Bee error: no model selected]"

        full_prompt = f"{BOBBY_BEE_SYSTEM}\n\nUser: {prompt}\nBobby Bee:"

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=60
            )
            if resp.status_code != 200:
                return f"[Bobby Bee error: HTTP {resp.status_code}]"

            data = resp.json()
            return data.get("response", "")

        except requests.exceptions.ConnectionError:
            self.ollama_online = False
            return "[Bobby Bee offline: Ollama not running]"
        except Exception as e:
            return f"[Bobby Bee error: {str(e)}]"

    # ---------------------------------------------------------
    # INTERNAL: DETECTION + CONFIG
    # ---------------------------------------------------------

    def _detect_ollama(self):
        """Ping Ollama and update online status + paths."""
        try:
            resp = requests.get(f"{self.base_url}/api/version", timeout=2)
            if resp.status_code == 200:
                self.ollama_online = True
                info = resp.json()

                # Extract paths if available
                self.install_path = info.get("install_path", self.install_path)
                self.model_path = info.get("model_path", self.model_path)

                self._save_location()
                return

        except Exception:
            pass

        # If we reach here, Ollama is offline
        self.ollama_online = False

    def _load_cached_location(self):
        """Load previously detected Ollama paths."""
        if not os.path.exists(CONFIG_PATH):
            return

        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                self.install_path = data.get("install_path")
                self.model_path = data.get("model_path")
        except Exception:
            pass

    def _save_location(self):
        """Persist detected Ollama paths."""
        os.makedirs("config", exist_ok=True)

        data = {
            "install_path": self.install_path,
            "model_path": self.model_path,
            "last_detected": datetime.utcnow().isoformat() + "Z"
        }

        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    # ---------------------------------------------------------
    # DISPATCHER BINDING
    # ---------------------------------------------------------

    def bind(self, dispatcher):
        """Store dispatcher reference."""
        self._dispatcher = dispatcher

    # ---------------------------------------------------------
    # PROVIDER HANDLER (CALLED BY DISPATCHER)
    # ---------------------------------------------------------

    def provider_handler(self, content: str, role: str):
        if self.observer_mode == "observer":
            response = self.observe(content)
        else:
            response = self.generate(content)
        message_id = f"local-{self._dispatcher._now_ms()}"
        self._dispatcher.on_provider_response("local", response, message_id)
