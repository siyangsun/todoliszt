"""
Parse metadata from Bitwig Studio .bwproject files.

FORMAT: .bwproject is a proprietary binary format (NOT a ZIP despite the name).
Magic bytes: b'BtWg'. The file contains a node tree encoding the project state.

CONFIRMED binary encoding (from reverse-engineering WHAT IS THIS SONG.bwproject):
  Node structure: <node_id: 2 bytes> <type: 1 byte> <value...>

  type 0x01 = bool/byte (1 byte value)
  type 0x05 = byte flag  (1 byte value)
  type 0x07 = double     (8 bytes, big-endian IEEE 754)
  type 0x08 = named container / string (4-byte BE length + UTF-8 bytes)
  type 0x09 = int32      (4 bytes, big-endian)

BPM: stored as type-07 double, node ID 0x02c8. The first 0x02c8 double in the file
  whose value falls in a plausible BPM range is the project tempo. (Older files also
  carry a b'\\x05TEMPO' text marker near it; newer Bitwig versions omit the marker,
  so we scan for the node pattern directly. Verified against 54 real projects.)

TIME SIGNATURE / BARS: encoding NOT yet confirmed. The Time Signature node (0x0176)
  is present in the file but the numerator/denominator are stored in an unclear format.
  Needs comparison of two projects with known different time signatures to decode.
  Returns None until confirmed.
"""
import os
import re
import struct
from typing import Optional

_MAGIC = b'BtWg'

# BPM node: id 0x02c8, type 0x07 (BE double). The node id recurs later in the
# file for other parameters (values like 0.0/0.5/1.0), so the range check is
# what disambiguates — the tempo is the first occurrence in plausible BPM range.
_BPM_NODE = b'\x02\xc8\x07'
_BPM_MIN = 20.0
_BPM_MAX = 999.0

# Plugin references appear as full filesystem paths to .dll / .vst3 / .clap
# files, scattered through the file — extracting them requires a full read.
# Anchoring the search at extension occurrences and walking back to the drive
# letter is ~20x faster than matching the path pattern at every position.
_PLUGIN_EXT_RE = re.compile(rb"\.(?:dll|vst3|clap)", re.IGNORECASE)
_PLUGIN_PATH_RE = re.compile(
    rb'[A-Za-z]:\\[^\x00-\x1f<>:"|?*]{2,240}\.(?:dll|vst3|clap)',
    re.IGNORECASE,
)


def parse(bwproject_path: str) -> dict:
    """Return dict with keys: bpm, plugins, time_sig_num, time_sig_denom,
    bars, length_seconds. Fields are None (plugins: []) if not found."""
    result = {
        "bpm": None,
        "plugins": [],
        "time_sig_num": None,
        "time_sig_denom": None,
        "bars": None,
        "length_seconds": None,
    }
    try:
        with open(bwproject_path, "rb") as f:
            data = f.read()
        if not data.startswith(_MAGIC):
            return result

        result["bpm"] = _extract_bpm(data)
        result["plugins"] = _extract_plugins(data)
        _derive_length(result)
    except Exception:
        pass
    return result


_BPM_NODE_RE = re.compile(re.escape(_BPM_NODE))


def _extract_bpm(data: bytes) -> Optional[float]:
    for m in _BPM_NODE_RE.finditer(data):
        try:
            val = struct.unpack_from(">d", data, m.end())[0]
        except struct.error:
            return None
        if _BPM_MIN <= val <= _BPM_MAX:
            return val
    return None


def _extract_plugins(data: bytes) -> list[str]:
    """Unique plugin names (path stems), e.g. 'Density64', 'Vital'."""
    names: dict[str, str] = {}
    for m in _PLUGIN_EXT_RE.finditer(data):
        window = max(0, m.start() - 244)
        colon = data.rfind(b":\\", window, m.start())
        if colon < 1:
            continue
        candidate = data[colon - 1 : m.end()]
        if not _PLUGIN_PATH_RE.fullmatch(candidate):
            continue
        try:
            path = candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        names.setdefault(stem.lower(), stem)
    return sorted(names.values(), key=str.lower)


def _derive_length(result: dict):
    if result["bpm"] and result["bars"]:
        beats_per_bar = result["time_sig_num"] or 4
        total_beats = result["bars"] * beats_per_bar
        result["length_seconds"] = (total_beats / result["bpm"]) * 60
