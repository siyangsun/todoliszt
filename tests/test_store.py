import json

import pytest

import data.store as store_mod
from data.store import Project, Store, fmt_date


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    # Redirect the module-level paths so tests never touch the real files
    monkeypatch.setattr(store_mod, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(store_mod, "_ENV_PATH", tmp_path / ".env")
    return tmp_path


def test_fresh_store_has_no_roots(isolated_paths):
    store = Store()
    assert store.root_folders == []
    assert store.bounce_folders == []


def test_env_bootstrap(isolated_paths):
    root = isolated_paths / "music"
    root.mkdir()
    (isolated_paths / ".env").write_text(f"ROOT_FOLDER={root}\n", encoding="utf-8")

    store = Store()
    assert store.root_folders == [str(root)]
    # Bootstrap persists to settings.json so .env is only needed once
    assert (isolated_paths / "settings.json").exists()


def test_env_not_used_when_settings_exist(isolated_paths):
    configured = isolated_paths / "configured"
    configured.mkdir()
    (isolated_paths / "settings.json").write_text(
        json.dumps({"root_folders": [str(configured)]}), encoding="utf-8"
    )
    (isolated_paths / ".env").write_text("ROOT_FOLDER=C:/somewhere/else", encoding="utf-8")

    store = Store()
    assert store.root_folders == [str(configured)]


def test_old_root_folder_key_migrated(isolated_paths):
    configured = isolated_paths / "configured"
    configured.mkdir()
    (isolated_paths / "settings.json").write_text(
        json.dumps({"root_folder": str(configured)}), encoding="utf-8"
    )

    store = Store()
    assert store.root_folders == [str(configured)]
    # Old key gone from in-memory settings
    assert "root_folder" not in store._settings


def test_tags_notes_survive_restart(isolated_paths):
    store = Store()
    store.root_folders = [str(isolated_paths / "music")]
    store.set_tags("Song", ["ambient", "wip"])
    store.set_notes("Song", "started as a jam")

    reloaded = Store()
    assert reloaded.get_user_data("Song") == (["ambient", "wip"], "started as a jam")


def test_data_lives_next_to_settings(isolated_paths):
    store = Store()
    store.root_folders = [str(isolated_paths / "music")]
    store.set_notes("Song", "hi")
    assert (isolated_paths / store_mod.DATA_FILENAME).exists()


def test_atomic_write_leaves_no_tmp(isolated_paths):
    store = Store()
    store.root_folders = [str(isolated_paths / "music")]
    store.set_tags("Song", ["x"])
    leftovers = list(isolated_paths.glob("*.tmp"))
    assert leftovers == []


def test_unknown_project_returns_empty(isolated_paths):
    store = Store()
    assert store.get_user_data("nope") == ([], "")


def test_theme_default_and_persist(isolated_paths):
    store = Store()
    assert store.theme == "Windows 7"
    store.theme = "Dark"
    store.save_settings()
    assert Store().theme == "Dark"


def test_fmt_date():
    assert fmt_date(None) == "—"
    assert fmt_date(0.0).startswith("19")  # epoch, local time


def _project(**kwargs):
    return Project(name="T", folder_path="p", bwproject_path="b", **kwargs)


def test_project_display_properties():
    p = _project(bpm=127.5, time_sig_num=3, time_sig_denom=4, length_seconds=204)
    assert p.bpm_str == "127.5"
    assert p.time_sig_str == "3/4"
    assert p.length_str == "3:24"

    empty = _project()
    assert empty.bpm_str == "—"
    assert empty.time_sig_str == "—"
    assert empty.length_str == "—"


def test_whole_bpm_has_no_decimal():
    assert _project(bpm=120.0).bpm_str == "120"
