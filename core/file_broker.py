# core/file_broker.py

import os


class FileBroker:
    """
    Gives the HUD read/write access to local project files.
    Claude API requests file operations through this broker.
    """

    ROOT = r"D:\AI\kaiju_hud"

    def read(self, relative_path: str) -> str:
        full_path = os.path.join(self.ROOT, relative_path)
        if not os.path.exists(full_path):
            return f"[FileBroker] File not found: {relative_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, relative_path: str, content: str) -> str:
        full_path = os.path.join(self.ROOT, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[FileBroker] Written: {relative_path}"

    def list_files(self, relative_dir: str = "") -> list:
        full_path = os.path.join(self.ROOT, relative_dir)
        result = []
        for root, dirs, files in os.walk(full_path):
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git"]]
            for file in files:
                if file.endswith(".py"):
                    rel = os.path.relpath(os.path.join(root, file), self.ROOT)
                    result.append(rel)
        return result