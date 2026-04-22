import os
import json


class SettingsManager:
    """
    Simple JSON-backed settings store.
    Loads on startup, saves on any change.
    No signals — other managers read from this on init.

    Stored fields:
      - API keys (claude, chatgpt, grok)
      - last_theme
      - last_glow
      - last_window_mode
      - columns (visibility dict)
      - hidden_prompt_enabled
      - hidden_prompt_profile
    """

    SETTINGS_PATH = os.path.join("config", "settings.json")
    HIDDEN_PROMPTS_PATH = os.path.join("config", "hidden_prompt_profiles.json")

    def __init__(self):
        self.settings = {
            "api_keys": {
                "claude": "",
                "chatgpt": "",
                "grok": ""
            },
            "last_theme": "classic",
            "last_glow": "subtle",
            "last_window_mode": "WI",
            "columns": {
                "claude": True,
                "chatgpt": True,
                "grok": True,
                "copilot": True,
                "local": True
            },
            "hidden_prompt_enabled": False,
            "hidden_prompt_profile": ""
        }

        self._load()

    # ---------------------------------------------------------
    # LOAD / SAVE
    # ---------------------------------------------------------

    def _load(self):
        """Load settings.json if it exists."""
        if not os.path.exists(self.SETTINGS_PATH):
            return

        try:
            with open(self.SETTINGS_PATH, "r") as f:
                data = json.load(f)
                self._merge_settings(data)
        except Exception:
            pass  # Graceful failure

    def save(self):
        """Write settings.json."""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.SETTINGS_PATH, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    # ---------------------------------------------------------
    # INTERNAL: MERGE LOADED SETTINGS
    # ---------------------------------------------------------

    def _merge_settings(self, data: dict):
        """Merge loaded settings into defaults safely."""
        for key, value in data.items():
            if key in self.settings:
                if isinstance(self.settings[key], dict) and isinstance(value, dict):
                    self.settings[key].update(value)
                else:
                    self.settings[key] = value

    # ---------------------------------------------------------
    # PUBLIC GETTERS / SETTERS
    # ---------------------------------------------------------

    def get_api_key(self, name: str) -> str:
        return self.settings["api_keys"].get(name, "")

    def set_api_key(self, name: str, key: str):
        self.settings["api_keys"][name] = key
        self.save()

    def get_last_theme(self) -> str:
        return self.settings["last_theme"]

    def set_last_theme(self, theme: str):
        self.settings["last_theme"] = theme
        self.save()

    def get_last_glow(self) -> str:
        return self.settings["last_glow"]

    def set_last_glow(self, glow: str):
        self.settings["last_glow"] = glow
        self.save()

    def get_last_window_mode(self) -> str:
        return self.settings["last_window_mode"]

    def set_last_window_mode(self, mode: str):
        self.settings["last_window_mode"] = mode
        self.save()

    def get_columns(self) -> dict:
        return self.settings["columns"].copy()

    def set_columns(self, columns: dict):
        self.settings["columns"] = columns.copy()
        self.save()

    def get_hidden_prompt_enabled(self) -> bool:
        return bool(self.settings.get("hidden_prompt_enabled", False))

    def set_hidden_prompt_enabled(self, enabled: bool):
        self.settings["hidden_prompt_enabled"] = bool(enabled)
        self.save()

    def get_hidden_prompt_profile(self) -> str:
        return str(self.settings.get("hidden_prompt_profile", "") or "")

    def set_hidden_prompt_profile(self, profile_name: str):
        self.settings["hidden_prompt_profile"] = str(profile_name or "")
        self.save()

    def get_hidden_prompt_profiles(self) -> dict:
        data = self._load_hidden_prompts()
        profiles = data.get("profiles", {})
        if isinstance(profiles, dict):
            return {str(k): str(v) for k, v in profiles.items()}
        return {}

    def save_hidden_prompt_profiles(self, profiles: dict):
        clean_profiles = {str(k): str(v) for k, v in profiles.items()}
        payload = {"profiles": clean_profiles}
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.HIDDEN_PROMPTS_PATH, "w") as f:
                json.dump(payload, f, indent=4)
        except Exception:
            pass

    def get_hidden_prompt_text(self, profile_name: str) -> str:
        if not profile_name:
            return ""
        profiles = self.get_hidden_prompt_profiles()
        return profiles.get(profile_name, "")

    def _load_hidden_prompts(self) -> dict:
        if not os.path.exists(self.HIDDEN_PROMPTS_PATH):
            return {"profiles": {}}
        try:
            with open(self.HIDDEN_PROMPTS_PATH, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"profiles": {}}
