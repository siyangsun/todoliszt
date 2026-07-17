"""
Diagnostic tool: inspect the binary node structure of a .bwproject file.

.bwproject is a proprietary binary format (magic b'BtWg'), NOT a ZIP.
Node encoding: <node_id: 2 bytes> <type: 1 byte> <value...>
See core/bwproject_parser.py for the confirmed type table.

Usage:
    python tools/inspect_bwproject.py <file.bwproject>
        Dump decodable nodes (offset, id, type, value).

    python tools/inspect_bwproject.py <a.bwproject> <b.bwproject>
        Diff mode: show nodes whose values differ between the two files.
        Use with two projects that differ in exactly one known way
        (e.g. time signature) to locate where that setting is stored.
"""
import struct
import sys

MAGIC = b"BtWg"

# type byte → (value size in bytes, decoder)
DECODERS = {
    0x01: (1, lambda b: b[0]),
    0x05: (1, lambda b: b[0]),
    0x07: (8, lambda b: struct.unpack(">d", b)[0]),
    0x09: (4, lambda b: struct.unpack(">i", b)[0]),
}


def iter_nodes(data: bytes, limit: int = 100_000):
    """Yield (offset, node_id, type, value) for every decodable node pattern.

    This is a heuristic scan — the format has no length-prefixed framing we
    know of, so false positives are expected. Filter by node id / plausible
    values when interpreting output.
    """
    n = 0
    for i in range(len(data) - 3):
        t = data[i + 2]
        if t not in DECODERS:
            continue
        size, decode = DECODERS[t]
        if i + 3 + size > len(data):
            continue
        node_id = (data[i] << 8) | data[i + 1]
        yield i, node_id, t, decode(data[i + 3 : i + 3 + size])
        n += 1
        if n >= limit:
            return


def load(path: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC):
        print(f"WARNING: {path} does not start with {MAGIC!r} (got {data[:4]!r})")
    return data


def dump(path: str):
    data = load(path)
    print(f"=== {path} ({len(data)} bytes) ===")
    print(f"{'offset':>8}  {'node':>6}  type  value")
    for off, node_id, t, val in iter_nodes(data):
        # Doubles that aren't round-ish garbage are the interesting ones
        if t == 0x07 and not (-1e6 < val < 1e6):
            continue
        print(f"{off:>8}  {node_id:#06x}  {t:#04x}  {val}")


def diff(path_a: str, path_b: str):
    a, b = load(path_a), load(path_b)

    def keyed(data):
        seen = {}
        occurrence = {}
        for off, node_id, t, val in iter_nodes(data):
            idx = occurrence.get((node_id, t), 0)
            occurrence[(node_id, t)] = idx + 1
            seen[(node_id, t, idx)] = (off, val)
        return seen

    nodes_a, nodes_b = keyed(a), keyed(b)
    print(f"=== nodes differing between\n  A: {path_a}\n  B: {path_b}\n===")
    print(f"{'node':>6}  type  {'occ':>4}  {'offset A':>8}  {'A':>14}  {'B':>14}")
    for key in sorted(nodes_a.keys() & nodes_b.keys()):
        (off_a, val_a), (_, val_b) = nodes_a[key], nodes_b[key]
        if val_a != val_b:
            node_id, t, idx = key
            print(f"{node_id:#06x}  {t:#04x}  {idx:>4}  {off_a:>8}  {val_a:>14}  {val_b:>14}")


def main():
    if len(sys.argv) == 2:
        dump(sys.argv[1])
    elif len(sys.argv) == 3:
        diff(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
