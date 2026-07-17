import os
import struct
import time
from pathlib import Path

import pytest

import core.scanner as scanner_mod
from core.scanner import scan
from data.store import Store


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner_mod, "CACHE_PATH", tmp_path / "cache.json")


def _make_store(roots, bounces=()):
    # Accepts a single path or a list; bypasses __init__ so tests never touch
    # the real settings.json
    store = Store.__new__(Store)
    if isinstance(roots, (str, Path)):
        roots = [roots]
    store._settings = {
        "root_folders": [str(r) for r in roots],
        "bounce_folders": [str(b) for b in bounces],
    }
    store._data = {}
    store._data_path = None
    return store


def _bwproject_bytes(bpm: float = 120.0) -> bytes:
    return b"BtWg" + b"\x02\xc8\x07" + struct.pack(">d", bpm)


def _make_project(root: Path, name: str, bpm: float = 120.0) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / f"{name}.bwproject").write_bytes(_bwproject_bytes(bpm))
    return folder


def test_finds_projects(tmp_path):
    _make_project(tmp_path, "Alpha", bpm=100.0)
    _make_project(tmp_path, "beta", bpm=150.0)
    (tmp_path / "not_a_project").mkdir()
    (tmp_path / "stray.txt").write_text("hi")

    projects = scan(_make_store(tmp_path))
    assert [p.name for p in projects] == ["Alpha", "beta"]
    assert projects[0].bpm == 100.0
    assert projects[1].bpm == 150.0


def test_missing_root_returns_empty(tmp_path):
    assert scan(_make_store(tmp_path / "gone")) == []


def test_prefers_bwproject_named_after_folder(tmp_path):
    folder = _make_project(tmp_path, "Song", bpm=120.0)
    (folder / "Old Version.bwproject").write_bytes(_bwproject_bytes(90.0))

    projects = scan(_make_store(tmp_path))
    assert projects[0].bpm == 120.0


def test_falls_back_to_newest_bwproject(tmp_path):
    folder = tmp_path / "Song"
    folder.mkdir()
    older = folder / "a.bwproject"
    newer = folder / "b.bwproject"
    older.write_bytes(_bwproject_bytes(90.0))
    newer.write_bytes(_bwproject_bytes(140.0))
    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    projects = scan(_make_store(tmp_path))
    assert projects[0].bpm == 140.0


def test_bounce_matching_recursive_and_case_insensitive(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    _make_project(root, "Song")

    bounces = tmp_path / "bounces"
    (bounces / "nested").mkdir(parents=True)
    (bounces / "Song_v1.wav").write_bytes(b"")
    (bounces / "SONG final.mp3").write_bytes(b"")
    (bounces / "nested" / "Song_v2.wav").write_bytes(b"")
    (bounces / "Other_v1.wav").write_bytes(b"")

    projects = scan(_make_store(root, bounces=[bounces]))
    names = [os.path.basename(p) for p in projects[0].bounce_files]
    assert sorted(names) == ["SONG final.mp3", "Song_v1.wav", "Song_v2.wav"]


def test_bounce_longest_project_name_wins(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    _make_project(root, "hihihi")
    _make_project(root, "hihihihihi")

    bounces = tmp_path / "bounces"
    bounces.mkdir()
    (bounces / "hihihi.wav").write_bytes(b"")
    (bounces / "hihihi2.wav").write_bytes(b"")
    (bounces / "hihihihihi bounce.wav").write_bytes(b"")

    projects = scan(_make_store(root, bounces=[bounces]))
    by_name = {p.name: [os.path.basename(f) for f in p.bounce_files] for p in projects}
    assert by_name["hihihi"] == ["hihihi.wav", "hihihi2.wav"]
    assert by_name["hihihihihi"] == ["hihihihihi bounce.wav"]


def test_corrupt_bwproject_does_not_kill_scan(tmp_path):
    _make_project(tmp_path, "Good", bpm=120.0)
    bad = tmp_path / "Bad"
    bad.mkdir()
    (bad / "Bad.bwproject").write_bytes(b"garbage")

    projects = scan(_make_store(tmp_path))
    assert [p.name for p in projects] == ["Bad", "Good"]
    assert projects[0].bpm is None
    assert projects[1].bpm == 120.0


def test_overlapping_bounce_folders_no_duplicates(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    _make_project(root, "Song")

    outer = tmp_path / "bounces"
    inner = outer / "nested"
    inner.mkdir(parents=True)
    (outer / "Song_v1.wav").write_bytes(b"")
    (inner / "Song_v2.wav").write_bytes(b"")

    # Both outer and inner configured — inner's files reachable via both walks
    projects = scan(_make_store(root, bounces=[outer, inner]))
    names = [os.path.basename(p) for p in projects[0].bounce_files]
    assert names == ["Song_v1.wav", "Song_v2.wav"]


def test_cache_skips_unchanged_files(tmp_path, monkeypatch):
    _make_project(tmp_path, "Song", bpm=140.0)
    store = _make_store(tmp_path)

    calls = []
    real_parse = scanner_mod.bwproject_parser.parse

    def counting_parse(path):
        calls.append(path)
        return real_parse(path)

    monkeypatch.setattr(scanner_mod.bwproject_parser, "parse", counting_parse)

    first = scan(store)
    assert len(calls) == 1
    second = scan(store)
    assert len(calls) == 1  # cache hit — file unchanged, no re-parse
    assert second[0].bpm == first[0].bpm == 140.0

    # Touch the file → mtime changes → re-parsed
    bw = tmp_path / "Song" / "Song.bwproject"
    now = time.time() + 10
    os.utime(bw, (now, now))
    scan(store)
    assert len(calls) == 2


def test_user_data_merged(tmp_path):
    _make_project(tmp_path, "Song")
    store = _make_store(tmp_path)
    store._data = {"Song": {"tags": ["ambient"], "notes": "wip"}}

    projects = scan(store)
    assert projects[0].tags == ["ambient"]
    assert projects[0].notes == "wip"


def test_multiple_roots_merged(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _make_project(root_a, "Alpha", bpm=100.0)
    _make_project(root_b, "Beta", bpm=130.0)

    projects = scan(_make_store([root_a, root_b]))
    names = [p.name for p in projects]
    assert "Alpha" in names
    assert "Beta" in names


def test_nested_root_finds_inner_projects(tmp_path):
    # Scanner is one-level deep, so a subfolder used as an explicit root
    # surfaces projects that would otherwise be invisible from the parent root.
    outer = tmp_path / "outer"
    inner = outer / "_the vault"
    inner.mkdir(parents=True)
    _make_project(outer, "OuterSong", bpm=100.0)
    _make_project(inner, "InnerSong", bpm=120.0)

    projects = scan(_make_store([outer, inner]))
    names = [p.name for p in projects]
    assert "OuterSong" in names
    assert "InnerSong" in names


def test_duplicate_project_path_not_doubled(tmp_path):
    # Same physical folder listed under two roots that both resolve to it
    # (pathological case — same path added twice)
    _make_project(tmp_path, "Song", bpm=120.0)
    projects = scan(_make_store([tmp_path, tmp_path]))
    assert len([p for p in projects if p.name == "Song"]) == 1
