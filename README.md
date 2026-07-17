# ToDoLiszt

A desktop project manager for Bitwig Studio. Browse your projects, view parsed metadata, add tags and notes, and track your bounce files — in a lightweight Windows-native UI.

![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)

## Features

- Browse all Bitwig projects from a configured root folder
- Auto-parses BPM from `.bwproject` files
- Add tags and notes per project — auto-saved, stored in a `todoliszt.json` file alongside your music
- Links bounce files to projects by filename prefix
- Sort by name, BPM, length, or modified date; filter live by name or tag
- Right-click menu, double-click to open folder in Explorer
- Windows Vista/7 aesthetic — native widgets, no web renderer, no Electron
- Ten themes, switchable live in Settings: **Windows 7** (native), **Bitwig**, **Dark**, **Zune**, **VS Code Dark+**, **Monokai**, **Synthwave**, **Dracula**, **Nord**, **Cyberpunk**

## Setup

```
pip install -r requirements.txt
```

Create a `.env` file next to `main.py`:

```
ROOT_FOLDER=C:\path\to\your\Bitwig Projects
```

Then run:

```
python main.py
```

On first launch the app reads `ROOT_FOLDER` from `.env`, writes `settings.json`, and scans your projects folder automatically. You can also configure everything via **Settings** in the toolbar.

## Storage

| File | Location | Purpose |
|------|----------|---------|
| `settings.json` | Next to `main.py` | Root folder + bounce folder paths |
| `todoliszt.json` | Inside your projects root | Tags and notes, keyed by project folder name |
| `.env` | Next to `main.py` | Bootstrap `ROOT_FOLDER` on first run |

`settings.json` and `.env` are gitignored. `todoliszt.json` lives with your music so it survives if you move the projects folder.

## Bounce file matching

Add one or more bounce folders in Settings. Any file (searched recursively) whose name starts with the project folder name is linked to that project and shown in the detail panel.

Example: project folder `MyTrack` matches `MyTrack_v1.wav`, `MyTrack_final.mp3`.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+F` | Focus search bar |
| `Escape` | Clear search / deselect project |
| `Ctrl+R` | Rescan projects folder |

## Stack

PyQt6 + Python stdlib. No database, no web renderer, no external dependencies beyond PyQt6.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest tests/
```

Covers the `.bwproject` binary parser, the scanner (project discovery, bounce matching), and the JSON store. The Qt UI layer is intentionally untested.

## Known limitations

- Time signature and bars are not yet parsed (`.bwproject` binary format partially reverse-engineered — BPM works, time sig encoding still unknown)
