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
    interval_wave_reinforced,
    wave_from_song_bank,
    render_wav,
    note_to_hz,
    NOTE_HZ,
    WAVE_SAMPLES,
)
from hugecodec.presets import PRESETS, PRESET_CATEGORIES  # noqa: E402


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


def test_nibble_hex_roundtrip() -> None:
    """Round-trip through the 32-char nibble-hex format hUGETracker uses."""
    print("\n== nibble-hex (hUGETracker HexWaveEdit format) round-trip ==")
    hex_str = "0d0c0200040b0e090302070a09080605080604080a0a070202080e0c0400020a"
    w = Wave.from_hex(hex_str)
    nibble_str = w.to_nibble_hex()
    check(len(nibble_str) == WAVE_SAMPLES,
          f"nibble-hex is exactly {WAVE_SAMPLES} chars  (got {len(nibble_str)})")
    check(all(c in "0123456789abcdef" for c in nibble_str),
          "nibble-hex is all lowercase hex")
    w2 = Wave.from_nibble_hex(nibble_str)
    check(w2 == w, "Wave → nibble-hex → Wave round-trips")

    # Explicit sanity check: the ith nibble-hex char is the ith wave sample
    # in hex. This is the property that matters for hUGETracker paste
    # compatibility (see tracker.pas :: HexWaveEditEditingDone).
    for i, s in enumerate(w.samples):
        check(int(nibble_str[i], 16) == s,
              f"nibble_str[{i}] = '{nibble_str[i]}' == sample[{i}] = {s}")


def test_nibble_hex_matches_hugetracker_convention() -> None:
    """Regression test for the paste-format bug.

    hUGETracker's HexWaveEdit reads one hex char per wave sample. Our old
    to_hex() format used one *byte* per nibble (upper nibble zeroed). When
    pasted, hUGETracker took the first 32 characters and turned them into
    a wave where every odd position was 0 — a different wave entirely.

    Fixed by exposing to_nibble_hex() as the paste-ready format.
    """
    print("\n== nibble-hex regression against paste bug ==")
    w = Wave.from_samples([1, 2, 3, 4, 5, 6, 7, 8,
                            9, 10, 11, 12, 13, 14, 15, 0,
                            1, 2, 3, 4, 5, 6, 7, 8,
                            9, 10, 11, 12, 13, 14, 15, 0])
    check(w.to_nibble_hex() == "123456789abcdef0123456789abcdef0",
          f"nibble-hex produces one char per sample "
          f"(got {w.to_nibble_hex()!r})")
    # And the byte-hex is what would have caused the paste bug:
    check(w.to_hex() == "0102030405060708090a0b0c0d0e0f00"
                       "0102030405060708090a0b0c0d0e0f00",
          "byte-hex is 64 chars (on-disk format)")


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
# render_wav                                                                  #
# --------------------------------------------------------------------------- #

def test_render_wav_header_and_frames() -> None:
    print("\n== render_wav produces well-formed WAV files ==")
    import io
    import wave as wavelib

    w = interval_wave("M3")
    data = render_wav(w, note_hz=NOTE_HZ["C5"], duration_s=1.0, sample_rate=44100)
    check(data[:4] == b"RIFF" and data[8:12] == b"WAVE",
          "starts with RIFF/WAVE magic")

    with wavelib.open(io.BytesIO(data), "rb") as f:
        check(f.getnchannels() == 1, "mono (1 channel)")
        check(f.getsampwidth() == 2, "16-bit samples")
        check(f.getframerate() == 44100, "44100 Hz sample rate")
        # Duration should be exactly 1.0s at 44100 Hz -> 44100 frames
        check(f.getnframes() == 44100,
              f"exactly 44100 frames for 1.0s (got {f.getnframes()})")


def test_render_wav_amplitude_bounds() -> None:
    print("\n== render_wav respects amplitude cap (no clipping past int16) ==")
    import wave as wavelib
    import io
    import struct

    # Full square wave via bin-1 dominant harmonic
    w = from_harmonics([(1, 1.0), (3, 1/3), (5, 1/5)])
    data = render_wav(w, note_hz=440.0, duration_s=0.5, amplitude=1.0)
    with wavelib.open(io.BytesIO(data), "rb") as f:
        raw = f.readframes(f.getnframes())
    frames = struct.unpack(f"<{len(raw)//2}h", raw)
    lo, hi = min(frames), max(frames)
    check(lo >= -32768 and hi <= 32767,
          f"all samples in int16 range  ({lo}..{hi})")
    # With amplitude=1.0 and fade envelope we should still see near-full swing
    peak = max(abs(lo), abs(hi))
    check(peak > 20000,
          f"reaches near-full amplitude at amp=1.0  (peak={peak})")


def test_render_wav_fade_prevents_clicks() -> None:
    print("\n== render_wav fade-in silence at start ==")
    import wave as wavelib
    import io
    import struct

    w = from_harmonics([(4, 1.0)])   # sine-like at bin 4 → strong signal
    data = render_wav(w, note_hz=440.0, duration_s=0.5, fade_ms=10.0)
    with wavelib.open(io.BytesIO(data), "rb") as f:
        raw = f.readframes(f.getnframes())
    frames = struct.unpack(f"<{len(raw)//2}h", raw)
    # First sample should be exactly zero (fade multiplier = 0/fade_n)
    check(frames[0] == 0, f"first sample = 0 (got {frames[0]})")
    # Last sample also faded (final index: pcm *= 0/fade_n)
    check(frames[-1] == 0, f"last sample = 0 (got {frames[-1]})")


def test_render_wav_rejects_bad_args() -> None:
    print("\n== render_wav rejects invalid arguments ==")
    w = interval_wave("M3")
    for bad_kwargs in [
        {"amplitude": 1.5},
        {"amplitude": -0.1},
        {"duration_s": 0},
        {"duration_s": -1},
        {"note_hz": 0},
        {"note_hz": -100},
        {"sample_rate": 0},
        {"sample_rate": -44100},
    ]:
        try:
            render_wav(w, **bad_kwargs)
            check(False, f"should have raised for {bad_kwargs}")
        except ValueError:
            check(True, f"raises ValueError for {bad_kwargs}")


def test_note_to_hz() -> None:
    print("\n== note_to_hz reference values (hUGETracker convention) ==")
    # A-6 in hUGETracker naming ≈ 440 Hz (scientific A4) — within ~0.5 Hz
    # due to integer N quantization at register value 1899.
    check(abs(note_to_hz("A6") - 440.0) < 0.5,
          f"A-6 ≈ 440 Hz  (got {note_to_hz('A6'):.4f})")
    # C-5 in hUGETracker naming ≈ 130.55 Hz (scientific C3)
    check(abs(note_to_hz("C5") - 130.55) < 0.01,
          f"C-5 = 130.55 Hz  (got {note_to_hz('C5'):.4f})")
    # C-7 in hUGETracker naming ≈ 524.29 Hz (scientific C5)
    check(abs(note_to_hz("C7") - 524.288) < 0.01,
          f"C-7 ≈ 524.29 Hz  (got {note_to_hz('C7'):.4f})")
    # Case + hyphen + '#' normalization
    check(abs(note_to_hz("c-5") - note_to_hz("C5")) < 1e-9,
          "'c-5' → C5 (case + hyphen normalized)")
    check(abs(note_to_hz("C#5") - note_to_hz("CS5")) < 1e-9,
          "'C#5' → CS5 (sharp normalized)")
    try:
        note_to_hz("X7")
        check(False, "should raise for unknown note")
    except KeyError:
        check(True, "raises KeyError for unknown note")


# --------------------------------------------------------------------------- #
# Preset registry                                                             #
# --------------------------------------------------------------------------- #

def test_presets_are_valid_waves() -> None:
    print("\n== all presets are valid 32-sample waves ==")
    for name, w in PRESETS.items():
        check(len(w.samples) == WAVE_SAMPLES,
              f"{name} has {WAVE_SAMPLES} samples")
        check(all(0 <= s <= 15 for s in w.samples),
              f"{name} samples in 0..15")


def test_preset_expected_top_bins() -> None:
    """Sanity: the top FFT bins should match each preset's design intent."""
    print("\n== presets have the harmonic content their names claim ==")
    expected: dict[str, set[int]] = {
        # Category A
        "dom7-narrow":            {4, 5, 6, 7},
        "dom7-wide":              {8, 10, 12, 14},
        "dom7-rolloff":           {4, 5, 6, 7},
        # Category B
        "maj7-just":              {8, 10, 12, 15},
        "maj7-leadingtone-hint":  {8, 10, 12, 15},
        "maj7-open":              {4, 5, 6, 15},
        # Category C
        "min7-truncated":         {10, 12, 15},
        "min7-septimal":          {6, 7, 9, 11},
        "min7-compressed":        {5, 6, 7, 9},
        # Category D
        "dim7-septimal":          {5, 6, 7, 8},
        # Category E
        "octave-up-sine":         {2},
        "thickener":              {2, 3, 4, 5},
        # Category F
        "p8":                     {1, 2},
        # Category G
        "formant-low":            {6, 7, 8},
        "formant-mid":            {7, 8, 9},
        "formant-high":           {8, 9, 10},
        "formant-low-rolloff":    {6, 7, 8},
        # Category H
        "metallic-7-11-13":       {7, 11, 13},
        "metallic-5-7-11":        {5, 7, 11},
        "metallic-3-7-11":        {3, 7, 11},
        # F1 reinforced dyads — dominant bins are still the primary dyad
        # (the octave-doubled bins are at 30% amp and rank lower).
        "reinforced-m3":          {5, 6},
        "reinforced-M3":          {4, 5},
        "reinforced-P4":          {3, 4},
        # F2 extended adjacent-bin dyads
        "dyad-6-7":               {6, 7},
        "dyad-7-8":               {7, 8},
        "dyad-8-9":               {8, 9},
        "dyad-9-10":              {9, 10},
        "dyad-10-11":             {10, 11},
    }
    for name, expected_bins in expected.items():
        w = PRESETS[name]
        r = analyze(w, top_n=len(expected_bins))
        top_bins = {p.bin for p in r.peaks[:len(expected_bins)]}
        check(top_bins == expected_bins,
              f"{name} top bins == {sorted(expected_bins)}  "
              f"(got {sorted(top_bins)})")


def test_preset_categories_cover_registry() -> None:
    print("\n== PRESET_CATEGORIES lists every registered preset exactly once ==")
    listed: list[str] = []
    for names in PRESET_CATEGORIES.values():
        listed.extend(names)
    check(sorted(listed) == sorted(PRESETS.keys()),
          "every preset in exactly one category")
    check(len(listed) == len(set(listed)),
          "no duplicates across categories")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> int:
    test_wave_io_roundtrip()
    test_nibble_hex_roundtrip()
    test_nibble_hex_matches_hugetracker_convention()
    test_fade_dyad_classification()
    test_interval_wave_synthesis()
    test_interval_wave_rejects_non_adjacent()
    test_from_harmonics_range_check()
    test_wave_rejects_wrong_size()
    test_render_wav_header_and_frames()
    test_render_wav_amplitude_bounds()
    test_render_wav_fade_prevents_clicks()
    test_render_wav_rejects_bad_args()
    test_note_to_hz()
    test_presets_are_valid_waves()
    test_preset_expected_top_bins()
    test_preset_categories_cover_registry()

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
