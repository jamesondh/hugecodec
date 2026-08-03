"""Regression harness for the sample-songs corpus.

Runs the reader against every `.uge` file in `~/hugetracker-sample-songs/` (or
a single file passed on the command line), verifies the parse succeeds and
that a few basic invariants hold, and prints a one-line summary per file.

Not pytest-based yet — kept as a plain script so it runs with just `python3`.

Usage:
    python3 tests/test_roundtrip.py                       # whole corpus
    python3 tests/test_roundtrip.py /path/to/song.uge     # single file
    python3 tests/test_roundtrip.py --verbose             # per-song details
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import traceback
from pathlib import Path

# Make src/ importable without install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hugecodec import read_song, Song  # noqa: E402


DEFAULT_CORPUS = Path.home() / "hugetracker-sample-songs"


def check_song(song: Song, path: Path) -> list[str]:
    """Return a list of problem strings; empty means all good."""
    problems = []

    # Every pattern key referenced in the order matrix must exist.
    for ch_idx, orders in enumerate(song.order_matrix):
        for pos, key in enumerate(orders):
            if key not in song.patterns:
                problems.append(f"ch{ch_idx} order[{pos}] references missing pattern key {key}")

    # Ticks per row must be positive (0 would divide by zero in the driver).
    for i, tpr in enumerate(song.ticks_per_row):
        if tpr <= 0:
            problems.append(f"ticks_per_row[{i}] is non-positive: {tpr}")

    # Each pattern must have exactly 64 cells.
    for k, p in song.patterns.items():
        if len(p.cells) != 64:
            problems.append(f"pattern {k} has {len(p.cells)} rows (expected 64)")

    # Waves must be 32 bytes each.
    for i, w in enumerate(song.waves):
        if len(w) != 32:
            problems.append(f"wave {i} is {len(w)} bytes (expected 32)")

    # Instrument banks must be 16 slots (0 unused).
    for label, bank in [("duty", song.duty_instruments),
                        ("wave", song.wave_instruments),
                        ("noise", song.noise_instruments)]:
        if len(bank) != 16:
            problems.append(f"{label}_instruments has {len(bank)} slots (expected 16)")

    return problems


def run_one(path: Path, verbose: bool) -> tuple[bool, str]:
    try:
        song = read_song(path)
    except Exception as e:
        if verbose:
            traceback.print_exc()
        return False, f"PARSE ERROR: {type(e).__name__}: {e}"

    problems = check_song(song, path)
    if problems:
        return False, "VALIDATION: " + "; ".join(problems)

    tpr = song.ticks_per_row[0] if len(set(song.ticks_per_row)) == 1 else song.ticks_per_row
    return True, f"V{song.source_version} pats={len(song.patterns)} orders={song.order_count()} tpr={tpr}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=None,
                        help="single .uge file (default: whole corpus)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()

    if args.path is not None:
        paths = [args.path]
    else:
        if not args.corpus.exists():
            print(f"corpus dir does not exist: {args.corpus}", file=sys.stderr)
            return 2
        paths = sorted(Path(p) for p in glob.glob(str(args.corpus / "*.uge")))

    if not paths:
        print("no files to check", file=sys.stderr)
        return 2

    ok_count = 0
    fail_count = 0
    for p in paths:
        ok, msg = run_one(p, args.verbose)
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}]  {p.name:60s}  {msg}")
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    print()
    print(f"{ok_count} passed, {fail_count} failed, {len(paths)} total")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
