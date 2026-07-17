import struct

from core.bwproject_parser import parse

RESULT_KEYS = {"bpm", "plugins", "time_sig_num", "time_sig_denom", "bars", "length_seconds"}


def _bpm_node(value: float) -> bytes:
    return b"\x02\xc8\x07" + struct.pack(">d", value)


def _write(tmp_path, payload: bytes) -> str:
    f = tmp_path / "test.bwproject"
    f.write_bytes(payload)
    return str(f)


def test_extracts_bpm(tmp_path):
    data = b"BtWg" + b"\x00" * 32 + _bpm_node(133.0) + b"\x00" * 8
    assert parse(_write(tmp_path, data))["bpm"] == 133.0


def test_skips_out_of_range_decoys(tmp_path):
    # The 0x02c8 node id recurs for non-tempo parameters with values like
    # 0.5 / 1.0 — the range check must skip those and find the real tempo
    data = b"BtWg" + _bpm_node(0.5) + _bpm_node(1.0) + _bpm_node(150.0)
    assert parse(_write(tmp_path, data))["bpm"] == 150.0


def test_fractional_bpm(tmp_path):
    data = b"BtWg" + _bpm_node(127.5)
    assert parse(_write(tmp_path, data))["bpm"] == 127.5


def test_wrong_magic_returns_none(tmp_path):
    data = b"ZIPX" + _bpm_node(120.0)
    assert parse(_write(tmp_path, data))["bpm"] is None


def test_no_bpm_node(tmp_path):
    data = b"BtWg" + b"\x00" * 64
    assert parse(_write(tmp_path, data))["bpm"] is None


def test_truncated_node_at_eof(tmp_path):
    # Node marker present but fewer than 8 value bytes follow
    data = b"BtWg" + b"\x02\xc8\x07" + b"\x00\x00"
    assert parse(_write(tmp_path, data))["bpm"] is None


def test_missing_file_returns_empty_result():
    result = parse("does/not/exist.bwproject")
    assert set(result) == RESULT_KEYS
    assert result["plugins"] == []
    assert all(v is None for k, v in result.items() if k != "plugins")


def test_result_keys(tmp_path):
    result = parse(_write(tmp_path, b"BtWg" + _bpm_node(120.0)))
    assert set(result) == RESULT_KEYS


def test_extracts_plugins_deduped_and_sorted(tmp_path):
    data = (
        b"BtWg" + _bpm_node(120.0)
        + b"\x00" * 4
        + rb"C:\Program Files\VST Plugins\Density64.dll"
        + b"\x00" * 4
        + rb"C:\Program Files\Common Files\VST3\Vital.vst3"
        + b"\x00" * 4
        + rb"C:\PROGRAM FILES\VST PLUGINS\DENSITY64.DLL"  # dupe, different case
    )
    result = parse(_write(tmp_path, data))
    assert result["plugins"] == ["Density64", "Vital"]


def test_no_plugins(tmp_path):
    result = parse(_write(tmp_path, b"BtWg" + _bpm_node(120.0)))
    assert result["plugins"] == []
