import json
import datetime
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"
_ENV_PATH = Path(__file__).parent.parent / ".env"
DATA_FILENAME = "todoliszt.json"


def _atomic_write_json(path: Path, payload: dict):
    # Write to a temp file then swap, so a crash mid-write can't corrupt the file
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)


def fmt_date(ts: float | None) -> str:
    if ts is None:
        return "—"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


@dataclass
class Project:
    name: str
    folder_path: str
    bwproject_path: str
    bpm: Optional[float] = None
    time_sig_num: Optional[int] = None
    time_sig_denom: Optional[int] = None
    bars: Optional[int] = None
    length_seconds: Optional[float] = None
    created: Optional[float] = None      # os.path.getctime result
    modified: Optional[float] = None     # os.path.getmtime result
    bwproject_title: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    custom_title: str = ""
    bounce_files: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)

    @property
    def length_str(self) -> str:
        if self.length_seconds is None:
            return "—"
        m, s = divmod(int(self.length_seconds), 60)
        return f"{m}:{s:02d}"

    @property
    def time_sig_str(self) -> str:
        if self.time_sig_num is None:
            return "—"
        return f"{self.time_sig_num}/{self.time_sig_denom}"

    @property
    def title(self) -> str:
        """Display title: custom > bwproject internal name > folder name."""
        if self.custom_title:
            return self.custom_title
        if self.bwproject_title:
            return self.bwproject_title
        return self.name

    @property
    def bpm_str(self) -> str:
        if self.bpm is None:
            return "—"
        return f"{self.bpm:g}"


class Store:
    def __init__(self):
        self._settings: dict = {}
        self._data: dict = {}
        self._data_path: Path = SETTINGS_PATH.parent / DATA_FILENAME
        self._load_settings()
        self._load_data()
        if not self.root_folders:
            self._bootstrap_from_env()

    # --- settings ---

    def _bootstrap_from_env(self):
        if not _ENV_PATH.exists():
            return
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ROOT_FOLDER="):
                    value = line[len("ROOT_FOLDER="):].strip()
                    if value:
                        self.root_folders = [value]
                        self.save_settings()
                    return

    def _load_settings(self):
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                self._settings = json.load(f)
        # Migrate old single root_folder key to list
        if "root_folder" in self._settings and "root_folders" not in self._settings:
            old = self._settings.pop("root_folder")
            self._settings["root_folders"] = [old] if old else []

    def save_settings(self):
        _atomic_write_json(SETTINGS_PATH, self._settings)

    @property
    def root_folders(self) -> list[str]:
        return self._settings.get("root_folders", [])

    @root_folders.setter
    def root_folders(self, value: list[str]):
        self._settings["root_folders"] = value

    @property
    def theme(self) -> str:
        return self._settings.get("theme", "Windows 7")

    @theme.setter
    def theme(self, value: str):
        self._settings["theme"] = value

    @property
    def bounce_folders(self) -> list[str]:
        return self._settings.get("bounce_folders", [])

    @bounce_folders.setter
    def bounce_folders(self, value: list[str]):
        self._settings["bounce_folders"] = value

    # --- user data ---

    def _load_data(self):
        if self._data_path and self._data_path.exists():
            with open(self._data_path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def _save_data(self):
        if self._data_path is None:
            return
        _atomic_write_json(self._data_path, self._data)

    def get_user_data(self, project_name: str) -> tuple[list[str], str, str]:
        entry = self._data.get(project_name, {})
        return entry.get("tags", []), entry.get("notes", ""), entry.get("custom_title", "")

    def set_tags(self, project_name: str, tags: list[str]):
        self._data.setdefault(project_name, {})["tags"] = tags
        self._save_data()

    def set_notes(self, project_name: str, notes: str):
        self._data.setdefault(project_name, {})["notes"] = notes
        self._save_data()

    def set_custom_title(self, project_name: str, title: str):
        self._data.setdefault(project_name, {})["custom_title"] = title
        self._save_data()
