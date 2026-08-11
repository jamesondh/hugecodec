"""Round-trip tests for `write_song`.

Two guarantees checked:

  1. **Semantic round-trip** on every V6 corpus file — the reader must
     accept the writer's output and produce a Song equal to the original.

  2. **Byte-diff bounded to ShortString padding** — the writer emits zeros
     in the bytes past each ShortString's length byte; the tracker leaves
     stack garbage. We verify that ALL byte differences fall inside a
     known-safe region (either a ShortString padding tail or a
     tracker-side non-canonical value we can characterize).

Also spot-checks the `playable_orders` / `set_playable_orders` helpers by
constructing a modified song and confirming the trailer is preserved.

Usage:
    python3 tests/test_writer.py                # all V6 corpus files
    python3 tests/test_writer.py --verbose
"""

from __future__ import annotations

import argparse
import glob
import struct
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hugecodec import read_song, write_song, Song  # noqa: E402
from hugecodec.json_dump import song_to_dict  # noqa: E402


DEFAULT_CORPUS = Path.home() / "hugetracker-sample-songs"


# --------------------------------------------------------------------------- #
# Semantic round-trip                                                         #
# --------------------------------------------------------------------------- #

def check_semantic_roundtrip(path: Path) -> str | None:
    """Read → write → read → compare dumps. Returns None on pass, message on fail."""
    orig_bytes = path.read_bytes()
    orig_song = read_song(orig_bytes)
    if orig_song.source_version not in (6, 7):
        return None  # not covered by the current writer
    rewritten_bytes = write_song(orig_song)
    reparsed = read_song(rewritten_bytes)

    a = song_to_dict(orig_song, include_defaults=True)
    b = song_to_dict(reparsed, include_defaults=True)
    if a != b:
        return _first_dict_diff(a, b)
    return None


def _first_dict_diff(a: dict, b: dict, path: str = "") -> str:
    """Return a short string describing the first divergence."""
    if type(a) is not type(b):
        return f"{path}: type mismatch {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a:
                return f"{path}.{k}: missing in orig"
            if k not in b:
                return f"{path}.{k}: missing in reparsed"
            sub = _first_dict_diff(a[k], b[k], f"{path}.{k}")
            if sub:
                return sub
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            sub = _first_dict_diff(x, y, f"{path}[{i}]")
            if sub:
                return sub
        return ""
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return ""


# --------------------------------------------------------------------------- #
# Byte-diff analysis                                                          #
# --------------------------------------------------------------------------- #

def analyze_byte_diffs(path: Path) -> dict:
    """Return a structured breakdown of where two byte sequences differ, so
    the caller can decide if the diff is benign (ShortString padding) or a
    real serialization bug.

    Classification is by *position*, not byte content: any diff whose offset
    falls inside a ShortString's padding tail (past the length byte's
    reported length) is benign — Pascal leaks arbitrary stack/heap memory
    there (ASCII fragments, integers, pointer values). The writer emits
    zeros; the reader ignores both sides.
    """
    orig = path.read_bytes()
    song = read_song(orig)
    if song.source_version not in (6, 7):
        return {"skip": True}
    rewritten = write_song(song)
    if len(orig) != len(rewritten):
        return {
            "size_matches": False,
            "orig_size": len(orig),
            "rewritten_size": len(rewritten),
        }

    padding_ranges = _shortstring_padding_ranges(orig, song.source_version)
    diff_positions = [i for i in range(len(orig)) if orig[i] != rewritten[i]]

    def in_padding(pos: int) -> bool:
        # bisect would be faster; corpus is small so linear is fine
        for start, end in padding_ranges:
            if start <= pos < end:
                return True
            if pos < start:
                return False
        return False

    ss_padding = sum(1 for i in diff_positions if in_padding(i))
    other = len(diff_positions) - ss_padding
    return {
        "total_diffs": len(diff_positions),
        "shortstring_padding": ss_padding,
        "other": other,
        "orig_size": len(orig),
        "rewritten_size": len(rewritten),
        "size_matches": True,
    }


def _shortstring_padding_ranges(data: bytes, version: int) -> list[tuple[int, int]]:
    """Return a sorted list of `(start, end)` half-open byte ranges covering
    every ShortString's undefined-padding tail in the file.

    Padding = the bytes past `length` inside each 256-byte ShortString buffer.
    For a name of length N, the padding range is
    `[shortstring_start + 1 + N, shortstring_start + 256)`.
    """
    if version not in (6, 7):
        return []
    ranges: list[tuple[int, int]] = []

    # 3 top-level ShortStrings: Name, Artist, Comment starting at offset 4
    pos = 4
    for _ in range(3):
        length = data[pos]
        ranges.append((pos + 1 + length, pos + 256))
        pos += 256

    # 45 instrument names — Name is the second field of TInstrumentV3, after
    # a 4-byte Type_ enum. Each TInstrumentV3 = 1385 bytes.
    for i in range(45):
        instr_start = pos + i * 1385
        name_start = instr_start + 4       # after Type_
        length = data[name_start]
        ranges.append((name_start + 1 + length, name_start + 256))

    return ranges


# --------------------------------------------------------------------------- #
# Trailer-helper spot check                                                   #
# --------------------------------------------------------------------------- #

def check_trailer_helpers() -> str | None:
    """Verify playable_orders / set_playable_orders correctly manage the
    trailer slot."""
    song = Song(source_version=6)
    song.order_matrix = [[5, 6, 7, 0], [1, 2, 0], [3, 0], [0]]
    if song.playable_orders(0) != [5, 6, 7]:
        return f"playable_orders(0): got {song.playable_orders(0)}, expected [5, 6, 7]"
    if song.playable_orders(1) != [1, 2]:
        return f"playable_orders(1): got {song.playable_orders(1)}, expected [1, 2]"
    if song.playable_orders(2) != [3]:
        return f"playable_orders(2): got {song.playable_orders(2)}, expected [3]"
    if song.playable_orders(3) != []:
        return f"playable_orders(3): got {song.playable_orders(3)}, expected []"

    song.set_playable_orders(0, [10, 20])
    if song.order_matrix[0] != [10, 20, 0]:
        return f"set_playable_orders trailer not appended: {song.order_matrix[0]}"

    song.set_playable_orders(1, [99], trailer=7)
    if song.order_matrix[1] != [99, 7]:
        return f"set_playable_orders custom trailer failed: {song.order_matrix[1]}"

    return None


# --------------------------------------------------------------------------- #
# Runner                                                                      #
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("path", nargs="?", type=Path, default=None,
                        help="single .uge file (default: whole corpus + love theme)")
    args = parser.parse_args()

    if args.path is not None:
        paths = [args.path]
    else:
        paths = sorted(Path(p) for p in glob.glob(str(args.corpus / "*.uge")))
        love = Path(__file__).resolve().parent.parent / "tmp" / "lovetheme-mother3.uge"
        if love.exists():
            paths.append(love)

    # 1) Trailer helper spot check
    print("Trailer helpers:")
    err = check_trailer_helpers()
    if err:
        print(f"  [FAIL] {err}")
        return 1
    print("  [PASS] playable_orders / set_playable_orders round-trip cleanly")
    print()

    # 2) Semantic round-trip on each V6/V7 file
    print("Semantic round-trip (read → write → read → dict equality):")
    sem_ok = sem_fail = sem_skip = 0
    for p in paths:
        try:
            diff = check_semantic_roundtrip(p)
        except Exception as e:
            if args.verbose:
                traceback.print_exc()
            print(f"  [ERROR] {p.name}: {type(e).__name__}: {e}")
            sem_fail += 1
            continue
        if diff is None:
            song = read_song(p.read_bytes())
            if song.source_version not in (6, 7):
                sem_skip += 1
                if args.verbose:
                    print(f"  [SKIP] {p.name}  (V{song.source_version}, writer not implemented)")
            else:
                sem_ok += 1
                if args.verbose:
                    print(f"  [PASS] {p.name}")
        else:
            print(f"  [FAIL] {p.name}: {diff}")
            sem_fail += 1
    print(f"  {sem_ok} passed, {sem_fail} failed, {sem_skip} skipped")
    print()

    # 3) Byte-diff analysis on each V6/V7 file
    print("Byte-diff analysis (goal: only ShortString padding differs):")
    byte_ok = byte_fail = 0
    for p in paths:
        try:
            info = analyze_byte_diffs(p)
        except Exception as e:
            print(f"  [ERROR] {p.name}: {type(e).__name__}: {e}")
            byte_fail += 1
            continue
        if info.get("skip"):
            continue
        if not info["size_matches"]:
            print(f"  [FAIL] {p.name}: size {info['orig_size']} vs {info['rewritten_size']}")
            byte_fail += 1
            continue
        if info["other"] > 0:
            print(f"  [FAIL] {p.name}: {info['other']} non-padding diffs "
                  f"(shortstring_padding={info['shortstring_padding']}, "
                  f"total={info['total_diffs']})")
            byte_fail += 1
        else:
            byte_ok += 1
            if args.verbose:
                print(f"  [PASS] {p.name}: {info['shortstring_padding']} padding diffs only")
    print(f"  {byte_ok} passed, {byte_fail} failed")

    return 0 if (sem_fail == 0 and byte_fail == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
