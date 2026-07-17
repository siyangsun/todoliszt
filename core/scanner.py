import json
import os
from pathlib import Path

from data.store import Project, Store, _atomic_write_json
from core import bwproject_parser

# Parsed-metadata cache keyed by project file path + (mtime, size).
# Machine-local derived data — lives next to main.py, gitignored.
CACHE_PATH = Path(__file__).parent.parent / "cache.json"

_EMPTY_PARSE = {
    "bpm": None, "plugins": [], "time_sig_num": None,
    "time_sig_denom": None, "bars": None, "length_seconds": None,
}


def scan(store: Store) -> list[Project]:
    roots = [os.path.normpath(r) for r in store.root_folders if os.path.isdir(r)]
    if not roots:
        return []

    all_bounce_files = _collect_bounce_files(store.bounce_folders)

    # Collect (entry, bwproject_path) across all roots; dedup by normalized folder path
    found: dict[str, tuple] = {}
    for root in roots:
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            bwproject_path = _find_bwproject(entry.path)
            if bwproject_path is not None:
                key = os.path.normcase(os.path.normpath(entry.path))
                if key not in found:
                    found[key] = (entry, bwproject_path)

    found_list = sorted(found.values(), key=lambda x: x[0].name.lower())

    bounce_map = _assign_bounces([e.name for e, _ in found_list], all_bounce_files)
    cache = _load_cache()
    new_cache = {}
    projects = []

    for entry, bwproject_path in found_list:
        try:
            stat = os.stat(bwproject_path)
        except OSError:
            continue
        key = os.path.normcase(os.path.normpath(bwproject_path))
        cached = cache.get(key)
        if (
            cached
            and cached.get("mtime") == stat.st_mtime
            and cached.get("size") == stat.st_size
        ):
            parsed = dict(_EMPTY_PARSE)
            parsed["bpm"] = cached.get("bpm")
            parsed["plugins"] = cached.get("plugins", [])
        else:
            try:
                parsed = bwproject_parser.parse(bwproject_path)
            except Exception:
                parsed = dict(_EMPTY_PARSE)
        new_cache[key] = {
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "bpm": parsed["bpm"],
            "plugins": parsed["plugins"],
        }
        tags, notes = store.get_user_data(entry.name)

        projects.append(Project(
            name=entry.name,
            folder_path=entry.path,
            bwproject_path=bwproject_path,
            bpm=parsed["bpm"],
            time_sig_num=parsed["time_sig_num"],
            time_sig_denom=parsed["time_sig_denom"],
            bars=parsed["bars"],
            length_seconds=parsed["length_seconds"],
            created=stat.st_ctime,
            modified=stat.st_mtime,
            tags=tags,
            notes=notes,
            bounce_files=bounce_map.get(entry.name, []),
            plugins=parsed["plugins"],
        ))

    _save_cache(new_cache)
    return projects



def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict):
    try:
        _atomic_write_json(CACHE_PATH, cache)
    except OSError:
        pass


def _find_bwproject(folder_path: str) -> str | None:
    candidates = [
        f for f in os.scandir(folder_path)
        if f.is_file() and f.name.endswith(".bwproject")
    ]
    if not candidates:
        return None
    # Prefer the file named after the folder, else the most recently modified
    expected = os.path.basename(folder_path).lower() + ".bwproject"
    for f in candidates:
        if f.name.lower() == expected:
            return f.path
    return max(candidates, key=lambda f: f.stat().st_mtime).path


def _collect_bounce_files(bounce_folders: list[str]) -> list[str]:
    # Dedupe by normalized path: configured folders may overlap (one nested
    # inside another), which would otherwise collect the same file repeatedly
    seen = {}
    for folder in bounce_folders:
        for dirpath, _dirnames, filenames in os.walk(folder):
            for name in filenames:
                path = os.path.join(dirpath, name)
                seen[os.path.normcase(os.path.normpath(path))] = path
    return list(seen.values())


def _assign_bounces(
    project_names: list[str], bounce_files: list[str]
) -> dict[str, list[str]]:
    """Map project name → bounce files, by filename prefix.

    When a filename prefix-matches several projects (e.g. "hihihihihi v2.wav"
    matches both "hihihi" and "hihihihihi"), the longest matching name wins —
    plain prefix matching otherwise, so no separator is required after the name.
    """
    by_lower = {n.lower(): n for n in project_names}
    prefixes = sorted(by_lower, key=len, reverse=True)
    mapping: dict[str, list[str]] = {}
    for path in bounce_files:
        base = os.path.basename(path).lower()
        for prefix in prefixes:
            if base.startswith(prefix):
                mapping.setdefault(by_lower[prefix], []).append(path)
                break
    return {name: sorted(paths) for name, paths in mapping.items()}
