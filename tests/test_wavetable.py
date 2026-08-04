#!/usr/bin/env python3
"""Tests for hugecodec.wavetable — Serum-shaped WAV emitter.

Runs as a plain script (no pytest dependency):
    python3 tests/test_wavetable.py

Exits non-zero on any failed check.
"""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from hugecodec.presets import PRESETS  # noqa: E402
from hugecodec.wavetable import (       # noqa: E402
    CURATED_PACKS,
    DEFAULT_VENDOR,
    SERUM_FRAME_SAMPLES,
    build_clm_chunk,
    expand_wave_zoh,
    parse_clm_chunk,
    write_serum_wavetable,
)
from hugecodec.waves import WAVE_SAMPLES, from_harmonics  # noqa: E402


FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        FAILURES.append(msg)


# --------------------------------------------------------------------------- #
# WAV chunk parsing helpers (test-side, minimal)                              #
# --------------------------------------------------------------------------- #

def parse_wav_chunks(data: bytes) -> dict[str, bytes]:
    """Return a dict of {chunk_id: chunk_body} from a RIFF WAV blob.

    Does not validate sizes exhaustively — just enough to sanity-check
    that we emit the chunks we claim to emit.
    """
    assert data[:4] == b"RIFF", "missing RIFF header"
    assert data[8:12] == b"WAVE", "missing WAVE form"
    out: dict[str, bytes] = {}
    i = 12
    while i < len(data):
        cid = data[i:i + 4].decode("ascii")
        size = struct.unpack("<I", data[i + 4:i + 8])[0]
        body = data[i + 8:i + 8 + size]
        out[cid] = body
        # Word-align: bump one extra byte if size is odd.
        i += 8 + size + (size % 2)
    return out


# --------------------------------------------------------------------------- #
# ZOH expansion                                                               #
# --------------------------------------------------------------------------- #

def test_expand_wave_zoh_shape() -> None:
    print("\n== ZOH expansion: shape and repeat structure ==")
    w = from_harmonics([(1, 1.0)])  # near-sine at bin 1
    expanded = expand_wave_zoh(w, frame_samples=SERUM_FRAME_SAMPLES,
                               remove_dc=False, amplitude=1.0)
    check(len(expanded) == SERUM_FRAME_SAMPLES,
          f"expanded length is {SERUM_FRAME_SAMPLES}")
    # Every 64-sample block should be constant (ZOH).
    hold = SERUM_FRAME_SAMPLES // WAVE_SAMPLES
    check(hold == 64, "hold = 2048 / 32 = 64 samples per nibble")
    all_constant = all(
        len(set(expanded[i * hold:(i + 1) * hold])) == 1
        for i in range(WAVE_SAMPLES)
    )
    check(all_constant, "each 64-sample block is constant (stair-step preserved)")


def test_expand_wave_zoh_dc_removal() -> None:
    print("\n== ZOH expansion: DC removal ==")
    w = from_harmonics([(3, 1.0)])
    expanded = expand_wave_zoh(w, remove_dc=True, amplitude=1.0)
    mean = sum(expanded) / len(expanded)
    check(abs(mean) < 1e-9, f"post-DC mean ~ 0 (got {mean:.2e})")
    peak = max(abs(x) for x in expanded)
    check(abs(peak - 1.0) < 1e-9, f"peak == 1.0 (got {peak:.6f})")


def test_expand_wave_zoh_silent() -> None:
    print("\n== ZOH expansion: silent wave ==")
    from hugecodec.waves import Wave
    silent = Wave(tuple([7] * WAVE_SAMPLES))
    expanded = expand_wave_zoh(silent, remove_dc=True, amplitude=1.0)
    check(all(x == 0.0 for x in expanded),
          "constant-nibble wave yields all-zero frame (no normalization blow-up)")


def test_expand_wave_zoh_rejects_bad_frame_size() -> None:
    print("\n== ZOH expansion: input validation ==")
    w = from_harmonics([(1, 1.0)])
    for bad in (0, -32, 33, 100, 2049):
        try:
            expand_wave_zoh(w, frame_samples=bad)
            check(False, f"frame_samples={bad} should have raised")
        except ValueError:
            check(True, f"frame_samples={bad} rejected")


# --------------------------------------------------------------------------- #
# clm chunk                                                                   #
# --------------------------------------------------------------------------- #

def test_clm_chunk_round_trip() -> None:
    print("\n== clm chunk: build + parse round-trip ==")
    chunk = build_clm_chunk(cycle_size=2048, interp=0, vendor="hugecodec")
    check(chunk.startswith(b"clm "),
          "chunk header is 'clm ' (four-char code with trailing space)")
    size = struct.unpack("<I", chunk[4:8])[0]
    payload = chunk[8:8 + size]
    parsed = parse_clm_chunk(payload)
    check(parsed["cycle_size"] == 2048, "round-tripped cycle_size = 2048")
    check(parsed["interp"] == 0, "round-tripped interp = 0")
    check(parsed["factory"] == 0,
          "factory flag is 0 (MUST NOT be 1 for user tables)")
    check(parsed["vendor"] == "hugecodec", "round-tripped vendor = hugecodec")


def test_clm_chunk_linear_interp() -> None:
    print("\n== clm chunk: linear interp mode ==")
    chunk = build_clm_chunk(interp=1)
    payload = chunk[8:8 + struct.unpack("<I", chunk[4:8])[0]]
    parsed = parse_clm_chunk(payload)
    check(parsed["interp"] == 1, "interp=1 lands in the B field")


def test_clm_chunk_matches_serum_shape() -> None:
    print("\n== clm chunk: matches Xfer's documented shape ==")
    # Xfer's own Basic Shapes.wav clm chunk: "<!>2048 01000000 wavetable (...)"
    # Our shape at interp=0: "<!>2048 00000000 hugecodec"
    chunk = build_clm_chunk(cycle_size=2048, interp=0, vendor="hugecodec")
    size = struct.unpack("<I", chunk[4:8])[0]
    payload = chunk[8:8 + size].decode("ascii")
    check(payload == "<!>2048 00000000 hugecodec",
          f"payload matches spec (got {payload!r})")


def test_clm_chunk_rejects_factory_flag() -> None:
    print("\n== clm chunk: no way to set factory flag through public API ==")
    # The build_clm_chunk API doesn't expose C — factory flag is hardcoded
    # to 0. This test guards against a regression where someone adds a
    # ``factory=`` param.
    chunk = build_clm_chunk(interp=0)
    payload = chunk[8:8 + struct.unpack("<I", chunk[4:8])[0]].decode("ascii")
    # Position of factory digit is index 7 (after "<!>2048 " and interp digit).
    check(payload[8] == "0",
          f"factory digit is '0' regardless of args (got {payload[8]!r})")


# --------------------------------------------------------------------------- #
# WAV assembly                                                                #
# --------------------------------------------------------------------------- #

def test_wav_single_frame_structure() -> None:
    print("\n== WAV: single-frame structure ==")
    w = from_harmonics([(1, 1.0)])
    blob = write_serum_wavetable([w], interp=0, vendor="hugecodec")
    chunks = parse_wav_chunks(blob)
    check("fmt " in chunks, "has fmt chunk")
    check("clm " in chunks, "has clm chunk")
    check("data" in chunks, "has data chunk")
    # data size = 2048 samples × 2 bytes (int16)
    check(len(chunks["data"]) == SERUM_FRAME_SAMPLES * 2,
          f"data chunk is {SERUM_FRAME_SAMPLES * 2} bytes for a 1-frame table")


def test_wav_multi_frame_concatenation() -> None:
    print("\n== WAV: multi-frame concatenation ==")
    frames = [PRESETS["formant-low"], PRESETS["formant-mid"], PRESETS["formant-high"]]
    blob = write_serum_wavetable(frames, interp=1)
    chunks = parse_wav_chunks(blob)
    expected = len(frames) * SERUM_FRAME_SAMPLES * 2
    check(len(chunks["data"]) == expected,
          f"data chunk is {expected} bytes for a 3-frame table")

    # Verify each frame's DC is ~zero (clean morphing).
    for i in range(len(frames)):
        start = i * SERUM_FRAME_SAMPLES * 2
        end = start + SERUM_FRAME_SAMPLES * 2
        samples = struct.unpack(f"<{SERUM_FRAME_SAMPLES}h",
                                chunks["data"][start:end])
        mean = sum(samples) / len(samples)
        check(abs(mean) < 2.0,
              f"frame {i} DC-removed (mean int16 = {mean:.2f}, ~0)")


def test_wav_fmt_chunk_content() -> None:
    print("\n== WAV: fmt chunk sanity ==")
    w = from_harmonics([(1, 1.0)])
    blob = write_serum_wavetable([w])
    chunks = parse_wav_chunks(blob)
    fmt = chunks["fmt "]
    fmt_code, n_ch, sr, byte_rate, block_align, bit_depth = struct.unpack(
        "<HHIIHH", fmt[:16]
    )
    check(fmt_code == 1, "PCM format code")
    check(n_ch == 1, "mono")
    check(sr == 44100, "44.1 kHz sample rate")
    check(bit_depth == 16, "16-bit")


def test_wav_size_efficiency() -> None:
    print("\n== WAV: size efficiency vs. old audition renders ==")
    w = from_harmonics([(3, 1.0)])
    blob = write_serum_wavetable([w])
    # Old audition WAVs are ~176KB (2s of int16 at 44.1kHz). We should be
    # dramatically smaller — target ~4-5 KB.
    check(len(blob) < 5000,
          f"single-frame wavetable < 5KB (got {len(blob)} bytes; "
          f"old audition renders were 176KB)")


def test_wav_rejects_empty_and_oversized_packs() -> None:
    print("\n== WAV: input validation ==")
    try:
        write_serum_wavetable([])
        check(False, "empty frames should have raised")
    except ValueError:
        check(True, "empty frames rejected")

    w = from_harmonics([(1, 1.0)])
    too_many = [w] * 257
    try:
        write_serum_wavetable(too_many)
        check(False, "257 frames should have raised (Serum max 256)")
    except ValueError:
        check(True, "> 256 frames rejected")


def test_wav_file_write_matches_bytes() -> None:
    print("\n== WAV: file-write matches in-memory bytes ==")
    w = PRESETS["formant-mid"]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = Path(f.name)
    try:
        blob = write_serum_wavetable([w], path=tmp)
        check(tmp.read_bytes() == blob, "written file bytes match return value")
    finally:
        tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Curated packs                                                               #
# --------------------------------------------------------------------------- #

def test_curated_packs_reference_valid_presets() -> None:
    print("\n== curated packs: all referenced presets exist ==")
    for pack_name, frame_names in CURATED_PACKS.items():
        for n in frame_names:
            check(n in PRESETS,
                  f"pack {pack_name!r} references known preset {n!r}")


def test_curated_packs_within_serum_limit() -> None:
    print("\n== curated packs: all under 256-frame Serum limit ==")
    for pack_name, frame_names in CURATED_PACKS.items():
        check(len(frame_names) <= 256,
              f"pack {pack_name!r} has {len(frame_names)} frames (<=256)")


def test_curated_packs_write_successfully() -> None:
    print("\n== curated packs: each writes as a valid Serum WAV ==")
    for pack_name, frame_names in CURATED_PACKS.items():
        waves = [PRESETS[n] for n in frame_names]
        blob = write_serum_wavetable(waves, interp=1)
        chunks = parse_wav_chunks(blob)
        check("clm " in chunks, f"pack {pack_name!r} has clm chunk")
        expected_bytes = len(waves) * SERUM_FRAME_SAMPLES * 2
        check(len(chunks["data"]) == expected_bytes,
              f"pack {pack_name!r} data size = {expected_bytes} bytes "
              f"({len(waves)} frames)")


# --------------------------------------------------------------------------- #
# Spectral preservation                                                       #
# --------------------------------------------------------------------------- #

def test_spectrum_preserved_through_zoh() -> None:
    """The bins-1..16 magnitudes of the original wave should be reflected
    in the low bins of the expanded frame's DFT. Test with a pure sine.
    """
    print("\n== spectrum preserved through ZOH expansion ==")
    import math

    w = from_harmonics([(4, 1.0)])  # bin 4 dominant
    expanded = expand_wave_zoh(w, remove_dc=True, amplitude=1.0)

    # At 2048 samples, the original bin 4 maps to bin 4 (since the wave
    # repeats 64 times across the 2048-sample window, but our expansion
    # holds one wave across the whole window → bin 4 stays at bin 4).
    #
    # Note: since the wave IS one cycle in the 2048-sample window,
    # a pure sine at wave-bin 4 shows up as a strong DFT bin 4 with
    # spectral copies at higher bins from the ZOH stair-step (which
    # Serum's mipmaps handle at playback time).
    def dft_mag(samples: list[float], k: int) -> float:
        n = len(samples)
        re = im = 0.0
        for i, x in enumerate(samples):
            angle = -2 * math.pi * k * i / n
            re += x * math.cos(angle)
            im += x * math.sin(angle)
        return math.sqrt(re * re + im * im)

    peak_bin = 4
    peak_energy = dft_mag(expanded, peak_bin) ** 2
    # Compare to nearby non-multiple bins that should be near-zero.
    noise_energy = sum(dft_mag(expanded, k) ** 2 for k in (1, 2, 3, 5, 6, 7))
    check(peak_energy > 10 * noise_energy,
          f"bin {peak_bin} dominates its low neighbors "
          f"(peak {peak_energy:.1f} vs noise {noise_energy:.1f})")


# --------------------------------------------------------------------------- #
# Runner                                                                      #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tests = [
        test_expand_wave_zoh_shape,
        test_expand_wave_zoh_dc_removal,
        test_expand_wave_zoh_silent,
        test_expand_wave_zoh_rejects_bad_frame_size,
        test_clm_chunk_round_trip,
        test_clm_chunk_linear_interp,
        test_clm_chunk_matches_serum_shape,
        test_clm_chunk_rejects_factory_flag,
        test_wav_single_frame_structure,
        test_wav_multi_frame_concatenation,
        test_wav_fmt_chunk_content,
        test_wav_size_efficiency,
        test_wav_rejects_empty_and_oversized_packs,
        test_wav_file_write_matches_bytes,
        test_curated_packs_reference_valid_presets,
        test_curated_packs_within_serum_limit,
        test_curated_packs_write_successfully,
        test_spectrum_preserved_through_zoh,
    ]
    for t in tests:
        t()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print(f"OK: all checks passed ({sum(1 for _ in tests)} test functions)")
