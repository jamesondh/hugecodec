"""Serum-2-shaped wavetable WAV emitter.

hUGETracker wave-channel presets can be dropped into Serum 2 to audition
timbres while composing in a modern DAW (FL Studio, etc.). Serum expects
each wavetable frame to be exactly ``SERUM_FRAME_SAMPLES`` (2048) samples,
and multi-frame wavetables concatenated back-to-back in one WAV file.

To signal "this is a pre-formatted wavetable, don't run frequency
estimation on it," we emit a RIFF ``clm `` (four-char code, trailing
space) chunk containing an ASCII payload of the form::

    <!>AAAA BC000000 D

where:
    AAAA — cycle size in samples (fixed at 2048)
    B    — interpolation type: 0 = none (stair-step), 1 = linear crossfade,
           2/3/4 = spectral modes (unused here)
    C    — Serum factory flag; MUST be 0 for user wavetables (1 is reserved
           for Xfer's factory content)
    000000 — six literal zeros
    D    — free-form vendor / comment string

Spec source: Steve Duda on KVR (2019). See NOTES.md § "Serum wavetable
export" for the sniff-tested reference chunk from Xfer's Basic Shapes.wav.

Frame construction
------------------
Each 32-sample GB wave is expanded to 2048 samples via **zero-order hold**
(each nibble repeated 64 times). This preserves the DAC stair-step
character exactly — no FFT smoothing, no invented harmonics. Serum's own
mipmap-based playback handles anti-aliasing at render time, so we don't
need to bandlimit at export.

DC removal
----------
Each frame's mean is subtracted before normalization, so multi-frame
wavetables morph cleanly (no click from stepping between frames with
different DC offsets). This is Serum's expected convention.

Frame normalization
-------------------
Each frame is scaled so its peak-absolute magnitude reaches
``amplitude`` (default 1.0 = full-scale, matching Xfer factory tables).
Per-frame normalization is required for morphable packs so quiet frames
don't sit at low amplitude relative to loud neighbours.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Sequence

from .waves import Wave, WAVE_SAMPLES

SERUM_FRAME_SAMPLES = 2048
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_VENDOR = "hugecodec"


# --------------------------------------------------------------------------- #
# Frame construction                                                          #
# --------------------------------------------------------------------------- #

def expand_wave_zoh(
    wave: Wave,
    frame_samples: int = SERUM_FRAME_SAMPLES,
    amplitude: float = 1.0,
    remove_dc: bool = True,
) -> list[float]:
    """Expand a 32-sample GB wave to ``frame_samples`` via zero-order hold.

    ``frame_samples`` must be a multiple of 32 (the wave cycle length). At
    the Serum default of 2048, each nibble is repeated 64 times.

    Returns a list of floats. If ``remove_dc``, the mean is subtracted
    before scaling. The result is peak-normalized to ``amplitude``. A
    fully-silent wave (constant nibble) returns all zeros regardless of
    ``amplitude``.
    """
    if frame_samples <= 0 or frame_samples % WAVE_SAMPLES != 0:
        raise ValueError(
            f"frame_samples must be a positive multiple of {WAVE_SAMPLES}, "
            f"got {frame_samples}"
        )
    if not (0.0 <= amplitude <= 1.0):
        raise ValueError(f"amplitude must be in [0, 1], got {amplitude}")

    hold = frame_samples // WAVE_SAMPLES

    # Expand each nibble ``hold`` times.
    expanded: list[float] = []
    for nibble in wave.samples:
        expanded.extend([float(nibble)] * hold)

    # DC removal.
    if remove_dc:
        mean = sum(expanded) / len(expanded)
        expanded = [x - mean for x in expanded]

    # Peak-normalize.
    peak = max(abs(x) for x in expanded)
    if peak == 0.0:
        return [0.0] * frame_samples
    scale = amplitude / peak
    return [x * scale for x in expanded]


# --------------------------------------------------------------------------- #
# clm chunk                                                                   #
# --------------------------------------------------------------------------- #

def build_clm_chunk(
    cycle_size: int = SERUM_FRAME_SAMPLES,
    interp: int = 0,
    vendor: str = DEFAULT_VENDOR,
) -> bytes:
    """Build the RIFF ``clm `` chunk (including the 8-byte header + payload).

    ``interp`` is Serum's B field: 0 = no interpolation (stair-step),
    1 = linear crossfade between frames. The Serum-factory flag (C) is
    always fixed at 0 here — setting it to 1 is reserved for Xfer's
    own factory content and can trigger unexpected import behaviour.

    ``vendor`` is a free-form ASCII comment; keep it short and printable.
    """
    if interp not in (0, 1, 2, 3, 4):
        raise ValueError(
            f"interp must be 0..4 (0=none, 1=linear, 2/3/4=spectral), "
            f"got {interp}"
        )
    if not (100 <= cycle_size <= 9999):
        # AAAA is a 4-char decimal field. Serum wavetables are 2048 in
        # practice; guard against nonsense values.
        raise ValueError(
            f"cycle_size must be a 3-4 digit int, got {cycle_size}"
        )
    if not vendor.isascii() or "\x00" in vendor:
        raise ValueError(f"vendor must be printable ASCII, got {vendor!r}")

    # Payload: "<!>2048 00000000 hugecodec"
    payload = f"<!>{cycle_size:04d} {interp}0000000 {vendor}".encode("ascii")

    # Chunk data must be word-aligned; RIFF pads odd-length chunks with a
    # trailing zero byte (the pad byte is NOT counted in the size field).
    size = len(payload)
    header = b"clm " + struct.pack("<I", size)
    pad = b"\x00" if size % 2 else b""
    return header + payload + pad


def parse_clm_chunk(payload: bytes) -> dict[str, str | int]:
    """Parse a clm chunk payload (not the 8-byte header — just the ASCII).

    Returns ``{"cycle_size": int, "interp": int, "factory": int, "vendor": str}``.
    Raises ``ValueError`` if the payload doesn't match Serum's shape. Used
    by the test suite for round-trip verification.
    """
    text = payload.decode("ascii", errors="strict")
    if not text.startswith("<!>"):
        raise ValueError(f"clm payload must start with '<!>', got {text[:8]!r}")
    # Format: "<!>AAAA BC000000 D..."
    body = text[3:]
    try:
        aaaa_str, bc_str, vendor = body.split(" ", 2)
    except ValueError as e:
        raise ValueError(f"clm payload malformed: {text!r}") from e
    if len(bc_str) != 8 or not bc_str.isdigit():
        raise ValueError(f"clm B/C field malformed: {bc_str!r}")
    return {
        "cycle_size": int(aaaa_str),
        "interp": int(bc_str[0]),
        "factory": int(bc_str[1]),
        "vendor": vendor,
    }


# --------------------------------------------------------------------------- #
# WAV writer                                                                  #
# --------------------------------------------------------------------------- #

def _pcm16(samples: Sequence[float]) -> bytes:
    """Convert [-1, 1] float samples to little-endian int16 PCM bytes."""
    out = bytearray(len(samples) * 2)
    for i, x in enumerate(samples):
        v = int(round(x * 32767.0))
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        struct.pack_into("<h", out, i * 2, v)
    return bytes(out)


def write_serum_wavetable(
    frames: Sequence[Wave],
    path: str | Path | None = None,
    *,
    interp: int = 0,
    vendor: str = DEFAULT_VENDOR,
    amplitude: float = 1.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    frame_samples: int = SERUM_FRAME_SAMPLES,
) -> bytes:
    """Write a Serum-shaped WAV containing one or more concatenated frames.

    Each frame is a 32-sample GB wave zero-order-hold-expanded to
    ``frame_samples`` (default 2048). Frames are DC-removed and
    peak-normalized independently so multi-frame morphing is click-free
    and each frame uses full headroom.

    The output includes a RIFF ``clm `` chunk between ``fmt `` and
    ``data`` so Serum recognizes the file as a pre-formatted wavetable
    (avoiding its sample-import frequency-estimation path).

    ``interp`` = 0 preserves the GB DAC stair-step; use 1 for multi-frame
    packs where you want linear crossfading between frames when morphing.

    Returns the WAV bytes; if ``path`` is given, also writes to disk.
    """
    if not frames:
        raise ValueError("frames must contain at least one Wave")
    if len(frames) > 256:
        raise ValueError(
            f"Serum wavetables max 256 frames, got {len(frames)}"
        )

    # --- Build the raw PCM data (frames concatenated, no separator) ------
    pcm_parts: list[bytes] = []
    for w in frames:
        floats = expand_wave_zoh(
            w,
            frame_samples=frame_samples,
            amplitude=amplitude,
            remove_dc=True,
        )
        pcm_parts.append(_pcm16(floats))
    pcm = b"".join(pcm_parts)

    # --- Build chunks ----------------------------------------------------
    bit_depth = 16
    n_channels = 1
    block_align = n_channels * bit_depth // 8
    byte_rate = sample_rate * block_align

    fmt_data = struct.pack(
        "<HHIIHH",
        1,             # PCM
        n_channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
    )
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_data)) + fmt_data

    clm_chunk = build_clm_chunk(
        cycle_size=frame_samples,
        interp=interp,
        vendor=vendor,
    )

    data_chunk = b"data" + struct.pack("<I", len(pcm)) + pcm
    # PCM data is even by construction (2 bytes/sample × N samples).

    # --- Assemble RIFF ---------------------------------------------------
    body = b"WAVE" + fmt_chunk + clm_chunk + data_chunk
    riff = b"RIFF" + struct.pack("<I", len(body)) + body

    if path is not None:
        Path(path).write_bytes(riff)
    return riff


# --------------------------------------------------------------------------- #
# Curated packs                                                               #
# --------------------------------------------------------------------------- #
# Multi-frame morphable wavetables built from the preset registry. Each
# pack picks an axis of variation that maps naturally onto Serum's WT
# position knob — dragging the knob walks through the timbre space.

CURATED_PACKS: dict[str, tuple[str, ...]] = {
    "dyads": (
        "dyad-6-7",
        "dyad-7-8",
        "dyad-8-9",
        "dyad-9-10",
        "dyad-10-11",
    ),
    "formants": (
        "formant-low-rolloff",
        "formant-low",
        "formant-mid",
        "formant-high",
    ),
    "seventh-chords": (
        "dom7-narrow",
        "dom7-rolloff",
        "dom7-wide",
        "maj7-just",
        "maj7-open",
        "maj7-leadingtone-hint",
        "min7-compressed",
        "min7-septimal",
        "min7-truncated",
        "dim7-septimal",
    ),
    "metallic": (
        "metallic-3-7-11",
        "metallic-5-7-11",
        "metallic-7-11-13",
    ),
    "reinforced": (
        "reinforced-m3",
        "reinforced-M3",
        "reinforced-P4",
    ),
}

PACK_DESCRIPTIONS: dict[str, str] = {
    "dyads":          "adjacent-bin dyad width sweep (bins 6:7 → 10:11)",
    "formants":       "vowel-like formant sweep low → high",
    "seventh-chords": "harmonic-cluster color axis — bright to dark",
    "metallic":       "coprime-prime inharmonic clusters, low → high anchor",
    "reinforced":     "close-interval octave-reinforced dyads (m3, M3, P4)",
}


__all__ = [
    "SERUM_FRAME_SAMPLES",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_VENDOR",
    "CURATED_PACKS",
    "PACK_DESCRIPTIONS",
    "expand_wave_zoh",
    "build_clm_chunk",
    "parse_clm_chunk",
    "write_serum_wavetable",
]
