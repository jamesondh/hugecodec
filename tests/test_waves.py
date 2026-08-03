#!/usr/bin/env python3
"""Tests for hugecodec.waves — spectral analysis + synthesis.

Runs as a plain script (no pytest dependency):
    python3 tests/test_waves.py

Exits non-zero on any failed check.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from hugecodec import read_song  # noqa: E402
from hugecodec.waves import (   # noqa: E402
    Wave,
    analyze,
    from_harmonics,
    interval_wave,
    wave_from_song_bank,
    WAVE_SAMPLES,
)


FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        FAILURES.append(msg)


# --------------------------------------------------------------------------- #
# Wave I/O round-trip                                                         #
# --------------------------------------------------------------------------- #

def test_wave_io_roundtrip() -> None:
    print("\n== Wave I/O round-trip ==")
    hex_str = "0d0c0200040b0e090302070a09080605080604080a0a070202080e0c0400020a"
    w = Wave.from_hex(hex_str)
    check(w.to_hex() == hex_str, "hex → Wave → hex round-trips")
    check(w.to_bytes() == bytes.fromhex(hex_str), "hex → Wave → bytes matches")
    w2 = Wave.from_bytes(w.to_bytes())
    check(w2 == w, "Wave → bytes → Wave round-trips")
    check(len(w.samples) == WAVE_SAMPLES, f"has {WAVE_SAMPLES} samples")


# --------------------------------------------------------------------------- #
# FADE waves classify correctly                                               #
# --------------------------------------------------------------------------- #

FADE_MICROPLASTICS = (
    Path.home() / "hugetracker-sample-songs" /
    "FADE - Microplastics in the Air.uge"
)


def test_fade_dyad_classification() -> None:
    print("\n== FADE 'minor'/'major'/'fourth' classify as expected ==")
    if not FADE_MICROPLASTICS.exists():
        print(f"  SKIP: {FADE_MICROPLASTICS} not found")
        return
    song = read_song(FADE_MICROPLASTICS)

    minor = wave_from_song_bank(song, 2)   # instrument 'minor' → bank[2]
    major = wave_from_song_bank(song, 3)   # 'major' → bank[3]
    fourth = wave_from_song_bank(song, 4)  # 'fourth' → bank[4]

    r_min = analyze(minor)
    r_maj = analyze(major)
    r_p4 = analyze(fourth)

    check(r_min.inferred_kind == "interval-m3",
          f"FADE 'minor' → interval-m3  (got {r_min.inferred_kind})")
    check(r_maj.inferred_kind == "interval-M3",
          f"FADE 'major' → interval-M3  (got {r_maj.inferred_kind})")
    check(r_p4.inferred_kind == "interval-P4",
          f"FADE 'fourth' → interval-P4  (got {r_p4.inferred_kind})")

    # Purity checks — FADE's dyads are extremely pure
    check(r_min.intervals and r_min.intervals[0].purity > 0.90,
          f"'minor' purity > 90%  (got {r_min.intervals[0].purity:.0%})")
    check(r_maj.intervals and r_maj.intervals[0].purity > 0.90,
          f"'major' purity > 90%  (got {r_maj.intervals[0].purity:.0%})")


# --------------------------------------------------------------------------- #
# Synthesis produces the expected spectral shape                              #
# --------------------------------------------------------------------------- #

def test_interval_wave_synthesis() -> None:
    print("\n== interval_wave() produces the expected spectra ==")
    for name, expected_bins in [("m3", (5, 6)), ("M3", (4, 5)),
                                ("P4", (3, 4)), ("P5", (2, 3))]:
        w = interval_wave(name)
        r = analyze(w)
        top2 = sorted(p.bin for p in r.peaks[:2])
        check(tuple(top2) == expected_bins,
              f"interval_wave({name!r}) → top-2 bins {expected_bins}  "
              f"(got {tuple(top2)})")
        check(r.inferred_kind == f"interval-{name}",
              f"interval_wave({name!r}) → interval-{name}  "
              f"(got {r.inferred_kind})")


def test_interval_wave_rejects_non_adjacent() -> None:
    print("\n== interval_wave() rejects non-adjacent-bin intervals ==")
    # Only m3/M3/P4/P5 are accepted after the perceptual-honesty cut.
    for bad_name in ["m6", "M6", "m7", "M7", "P8", "m2", "M2", "tritone"]:
        try:
            interval_wave(bad_name)
            check(False, f"interval_wave({bad_name!r}) should have raised")
        except ValueError:
            check(True, f"interval_wave({bad_name!r}) raises ValueError")


def test_from_harmonics_range_check() -> None:
    print("\n== from_harmonics rejects out-of-range bins ==")
    try:
        from_harmonics([(17, 1.0)])
        check(False, "should raise for bin > Nyquist")
    except ValueError:
        check(True, "raises for bin > Nyquist (17)")

    try:
        from_harmonics([(0, 1.0)])
        check(False, "should raise for bin 0 (DC)")
    except ValueError:
        check(True, "raises for bin 0 (DC)")


# --------------------------------------------------------------------------- #
# Sample-size guardrails                                                      #
# --------------------------------------------------------------------------- #

def test_wave_rejects_wrong_size() -> None:
    print("\n== Wave construction guardrails ==")
    try:
        Wave(samples=tuple(range(20)))
        check(False, "should reject wrong sample count")
    except ValueError:
        check(True, "rejects wrong sample count")

    try:
        Wave.from_hex("00" * 20)
        check(False, "should reject wrong hex length")
    except ValueError:
        check(True, "rejects wrong hex length")

    try:
        Wave(samples=tuple([0] * 31 + [16]))
        check(False, "should reject sample > 15")
    except ValueError:
        check(True, "rejects sample > 15")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> int:
    test_wave_io_roundtrip()
    test_fade_dyad_classification()
    test_interval_wave_synthesis()
    test_interval_wave_rejects_non_adjacent()
    test_from_harmonics_range_check()
    test_wave_rejects_wrong_size()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
