# core/file_broker.py

import os
from pathlib import Path


class FileBroker:
    """
    Gives the HUD read/write access to local project files.
    Claude API requests file operations through this broker.

    ROOT is always resolved relative to this file's location — never
    hardcoded. file_broker.py lives at kaiju_hud/core/file_broker.py,
    so two levels up is the kaiju_hud/ application root.
    """

    def __init__(self):
        # Resolve root dynamically: kaiju_hud/core/file_broker.py
        #   .parent   → kaiju_hud/core/
        #   .parent   → kaiju_hud/           (application root)
        self.ROOT = Path(__file__).resolve().parent.parent

        # Ensure Projects/ always exists at the application root on startup
        (self.ROOT / "Projects").mkdir(exist_ok=True)

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    def read(self, relative_path: str) -> str:
        full_path = self.ROOT / relative_path
        if not full_path.exists():
            return f"[FileBroker] File not found: {relative_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------

    def write(self, relative_path: str, content: str) -> str:
        full_path = self.ROOT / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[FileBroker] Written: {relative_path}"

    # ---------------------------------------------------------
    # LIST FILES
    # ---------------------------------------------------------

    def list_files(self, relative_dir: str = "") -> list:
        full_path = self.ROOT / relative_dir if relative_dir else self.ROOT
        result = []
        for root, dirs, files in os.walk(full_path):
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git"]]
            for file in files:
                if file.endswith(".py"):
                    rel = os.path.relpath(
                        os.path.join(root, file), str(self.ROOT)
                    )
                    result.append(rel)
        return result

    # ---------------------------------------------------------
    # PROJECT FOLDER (Stage 1)
    # ---------------------------------------------------------

    def ensure_project_folder(self, project_name: str) -> str:
        """
        Creates Projects/[project_name]/ under ROOT if it doesn't exist.
        Returns the relative path string: "Projects/[project_name]"
        """
        folder = self.ROOT / "Projects" / project_name
        folder.mkdir(parents=True, exist_ok=True)
        return str(Path("Projects") / project_name)
