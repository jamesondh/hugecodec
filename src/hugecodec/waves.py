"""Wave analysis and synthesis for hUGETracker wave-channel instruments.

hUGETracker waves are 32 samples of 4-bit resolution stored as 32 bytes on disk
(one nibble per byte, upper nibble always zero — see NOTES.md). When played on
the Game Boy wave channel, the 32-sample cycle repeats at the note frequency,
so the wave's frequency-domain content (bins 1..16) shows up as harmonic
partials above that fundamental.

This module gives you:

  Wave             — 32-sample wave with hex / bytes / int-list I/O
  analyze()        — DFT-based spectral report (peak bins, detected intervals)
  from_harmonics() — additive-synthesis designer: (bin, amp[, phase]) list.
                     Honest low-level API — makes no claims about what the
                     resulting sound will be perceived as.
  interval_wave()  — FADE-style close-bin dyad. Only accepts the four
                     adjacent-bin intervals that reliably read as two
                     audible pitches: m3 (5:6), M3 (4:5), P4 (3:4),
                     P5 (2:3). Wider ratios are perceptually unreliable
                     on this channel — use from_harmonics() instead and
                     don't expect a named interval.

Deliberately NOT provided: `triad_wave`, `seventh_wave`, or any "chord"
constructor. A single 32-sample periodic waveform is one pitched source,
not multiple voices — bins 10:12:15 aren't a minor chord, they're partials
9-15 of the tracker note, and the ear treats them that way (missing
fundamental illusion). See NOTES.md "Wave-channel sample interpretation".

Everything is stdlib-only. The DFT is O(N²) but N=32 so it doesn't matter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

WAVE_SAMPLES = 32          # samples per wave cycle
WAVE_MAX = 15              # 4-bit maximum value
NYQUIST_BIN = WAVE_SAMPLES // 2   # 16 — highest addressable partial


# Adjacent-bin interval ratios that reliably read as two audible pitches on
# the wave channel. These are FADE's four cases plus P5 (bins 2:3, also seen
# in Microplastics' "Sine wave"). Wider ratios exist mathematically but on
# 32 samples × 4 bits they tend to collapse into a single colored timbre
# rather than two distinguishable pitches. Use from_harmonics() if you want
# to experiment outside this set.
#
# Each entry maps a canonical name to (numerator, denominator) with num > den.
# The wave uses adjacent bins (den, num) — e.g. m3 = (6, 5) → bins 5:6.
INTERVAL_RATIOS: dict[str, tuple[int, int]] = {
    "m3":  (6, 5),
    "M3":  (5, 4),
    "P4":  (4, 3),
    "P5":  (3, 2),
}

_INTERVAL_ALIASES: dict[str, str] = {
    "minor": "m3", "minor3": "m3", "min3": "m3",
    "major": "M3", "major3": "M3", "maj3": "M3",
    "fourth": "P4", "perfect4": "P4",
    "fifth":  "P5", "perfect5": "P5",
}


# --------------------------------------------------------------------------- #
# Wave dataclass                                                              #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Wave:
    """A 32-sample, 4-bit-per-sample Game Boy wave.

    Samples are stored as a tuple of ints in 0..15. Construction paths:
      Wave(samples=[...])        # direct
      Wave.from_hex("0b0e...")   # 64 hex chars, one nibble per pair
      Wave.from_bytes(b"...")    # 32 bytes, one nibble per byte
    """
    samples: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.samples) != WAVE_SAMPLES:
            raise ValueError(
                f"Wave must have {WAVE_SAMPLES} samples, got {len(self.samples)}"
            )
        for i, s in enumerate(self.samples):
            if not (0 <= s <= WAVE_MAX):
                raise ValueError(f"sample[{i}]={s} out of 0..{WAVE_MAX}")

    # -- constructors -------------------------------------------------------

    @classmethod
    def from_hex(cls, s: str) -> "Wave":
        s = s.strip().lower()
        if len(s) != WAVE_SAMPLES * 2:
            raise ValueError(
                f"hex must be {WAVE_SAMPLES * 2} chars, got {len(s)}"
            )
        return cls(tuple(int(s[2*i:2*i+2], 16) for i in range(WAVE_SAMPLES)))

    @classmethod
    def from_bytes(cls, b: bytes) -> "Wave":
        if len(b) != WAVE_SAMPLES:
            raise ValueError(
                f"bytes must be {WAVE_SAMPLES} long, got {len(b)}"
            )
        return cls(tuple(int(x) for x in b))

    @classmethod
    def from_samples(cls, samples: Iterable[int]) -> "Wave":
        return cls(tuple(int(x) for x in samples))

    # -- exporters ----------------------------------------------------------

    def to_hex(self) -> str:
        return "".join(f"{s:02x}" for s in self.samples)

    def to_bytes(self) -> bytes:
        return bytes(self.samples)

    def to_list(self) -> list[int]:
        return list(self.samples)

    # -- spectrum -----------------------------------------------------------

    def dft_magnitude(self) -> list[float]:
        """DC-removed DFT magnitudes for bins 0..N/2 (inclusive).

        Bin 0 is always 0 (DC removed). Bin k corresponds to a partial that
        completes k full cycles across the 32-sample window — audible as k×
        the note frequency when played on the Game Boy wave channel.
        """
        N = WAVE_SAMPLES
        mean = sum(self.samples) / N
        ac = [x - mean for x in self.samples]
        out: list[float] = []
        for k in range(N // 2 + 1):
            re = im = 0.0
            for n in range(N):
                angle = -2 * math.pi * k * n / N
                re += ac[n] * math.cos(angle)
                im += ac[n] * math.sin(angle)
            out.append(math.sqrt(re * re + im * im))
        return out

    # -- pretty printing ----------------------------------------------------

    def ascii_shape(self, cols: int = WAVE_SAMPLES, rows: int = 16) -> list[str]:
        """Render an ASCII plot of the wave (rows-tall × 32-wide by default)."""
        assert cols == WAVE_SAMPLES, "downsampling not implemented"
        step = WAVE_MAX / max(rows - 1, 1)
        out = []
        for r in range(rows - 1, -1, -1):
            threshold = r * step
            out.append("".join(
                "#" if s >= threshold else " " for s in self.samples
            ))
        return out


# --------------------------------------------------------------------------- #
# Analysis                                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class PeakBin:
    bin: int
    magnitude: float


@dataclass
class DetectedInterval:
    """Interval implied by two dominant, adjacent bins."""
    bin_low: int
    bin_high: int
    ratio_num: int          # reduced numerator (=bin_high / gcd)
    ratio_den: int          # reduced denominator (=bin_low / gcd)
    interval_name: str      # e.g. 'm3', 'P4', or 'unknown'
    purity: float           # fraction of AC energy carried by these two bins


@dataclass
class WaveReport:
    """Summary of a wave's spectral character."""
    dc_offset: float
    ac_energy: float
    peaks: list[PeakBin]                     # top-N bins by magnitude
    intervals: list[DetectedInterval]        # 0, 1, or 2 detected intervals
    inferred_kind: str                       # human-readable kind
    description: str                         # one-line prose summary


def _reduce(a: int, b: int) -> tuple[int, int]:
    g = math.gcd(a, b)
    return a // g, b // g


def _lookup_interval(a: int, b: int) -> str:
    """Given a reduced ratio a:b (b > a), return canonical interval name."""
    if a > b:
        a, b = b, a
    target = (b, a)
    for name, ratio in INTERVAL_RATIOS.items():
        if ratio == target:
            return name
    return "unknown"


def analyze(wave: Wave, top_n: int = 6, purity_threshold: float = 0.55) -> WaveReport:
    """Spectrally analyze a wave. Detects FADE-style interval waves.

    An "interval wave" is one where two ADJACENT-OR-CLOSE bins (gap ≤ 2)
    carry the majority of the AC energy. `purity_threshold` controls how
    concentrated the energy has to be. Non-adjacent dominant-pair waves
    (e.g. organ stacks, pulse waves) are classified separately.
    """
    mags = wave.dft_magnitude()
    total_ac = sum(m * m for m in mags[1:])  # skip DC
    dc = sum(wave.samples) / WAVE_SAMPLES

    # Rank non-DC bins
    ranked = sorted(range(1, len(mags)), key=lambda k: mags[k], reverse=True)
    peaks = [PeakBin(bin=k, magnitude=mags[k]) for k in ranked[:top_n]]

    intervals: list[DetectedInterval] = []
    if len(ranked) >= 2 and total_ac > 0:
        k1, k2 = ranked[0], ranked[1]
        pair_energy = mags[k1] ** 2 + mags[k2] ** 2
        purity = pair_energy / total_ac
        num, den = _reduce(max(k1, k2), min(k1, k2))
        name = _lookup_interval(num, den)
        # Only count as a "dyad interval" if the two peaks are close together
        # (adjacent or one-bin gap). Bigger spreads = organ/pulse patterns.
        is_close_pair = abs(k1 - k2) <= 2
        if purity >= purity_threshold and is_close_pair:
            intervals.append(DetectedInterval(
                bin_low=min(k1, k2),
                bin_high=max(k1, k2),
                ratio_num=num,
                ratio_den=den,
                interval_name=name,
                purity=purity,
            ))

    # Inference / description — pass the full DFT, not just top-N
    inferred, desc = _infer_kind(wave, mags, total_ac, peaks, intervals)

    return WaveReport(
        dc_offset=dc,
        ac_energy=math.sqrt(total_ac),
        peaks=peaks,
        intervals=intervals,
        inferred_kind=inferred,
        description=desc,
    )


def _odd_harmonic_fraction(mags: list[float], total_ac: float) -> float:
    """Energy fraction concentrated in odd-numbered bins (1, 3, 5, 7…).

    A perfect square wave has 100% odd-harmonic energy with amplitudes rolling
    off as 1/n. A perfect triangle wave also lives on odd bins but rolls off
    faster (1/n²). Anything above ~0.9 is a strong pulse-family signature.
    """
    if total_ac == 0:
        return 0.0
    odd = sum(mags[k] ** 2 for k in range(1, len(mags)) if k % 2 == 1)
    return odd / total_ac


def _infer_kind(wave: Wave,
                mags: list[float],
                total_ac: float,
                peaks: list[PeakBin],
                intervals: list[DetectedInterval]) -> tuple[str, str]:
    """Heuristic classification for the report's `inferred_kind`."""
    if total_ac == 0 or not peaks:
        return ("silent", "silent (no AC content)")

    top_bin = peaks[0].bin
    top_energy = peaks[0].magnitude ** 2

    # Single-partial: >90% of TOTAL AC energy in one bin
    if top_energy / total_ac > 0.90:
        if top_bin == 1:
            return ("sine-fundamental", "near-sine at fundamental (bin 1)")
        return (f"single-partial-b{top_bin}",
                f"near-single partial at bin {top_bin} — "
                f"sounds {top_bin}× above tracker note")

    # Pulse/square: dominant bin 1 + strong odd-harmonic energy
    odd_frac = _odd_harmonic_fraction(mags, total_ac)
    if top_bin == 1 and odd_frac > 0.85:
        # Distinguish pulse from triangle by 1/n vs 1/n² roll-off
        # Cheap proxy: ratio bin_3 / bin_1
        b3_ratio = (mags[3] / mags[1]) if len(mags) > 3 and mags[1] > 0 else 0
        if b3_ratio > 0.2:
            return ("pulse", f"pulse / square wave (bin 1 fundamental + odd harmonics, "
                             f"{odd_frac:.0%} odd)")
        return ("triangle", f"triangle-like (bin 1 fundamental + weak odd harmonics, "
                            f"{odd_frac:.0%} odd)")

    # FADE-style adjacent-bin interval dyad
    if intervals:
        iv = intervals[0]
        if iv.interval_name != "unknown":
            return (f"interval-{iv.interval_name}",
                    f"interval dyad {iv.interval_name} "
                    f"(bins {iv.bin_low}:{iv.bin_high}, purity {iv.purity:.0%})")
        return ("interval-unknown",
                f"two-partial wave at bins {iv.bin_low}:{iv.bin_high} "
                f"(ratio {iv.ratio_num}:{iv.ratio_den})")

    # Fall through: describe by top-3 peak bins as a "harmonic mix"
    # (a single pitched timbre with an unusual partial distribution — this
    # is where multi-bin additive designs land, not chord territory)
    top3_str = ":".join(str(p.bin) for p in peaks[:3])
    return ("harmonic-mix", f"harmonic mix, dominant bins {top3_str}")


# --------------------------------------------------------------------------- #
# Synthesis                                                                   #
# --------------------------------------------------------------------------- #

def from_harmonics(
    harmonics: Sequence[tuple[int, float] | tuple[int, float, float]],
    dc: float = 7.5,
) -> Wave:
    """Additive synthesis: sum sines at given bins, quantize to 4 bits.

    Each harmonic is (bin_k, amplitude) or (bin_k, amplitude, phase_degrees).
    The result is auto-normalized so it uses the full 0..15 range regardless
    of amplitudes, then rounded to nibbles.

    `dc` is the DC bias (default 7.5, the mid-range). Rarely worth changing.
    """
    if not harmonics:
        return Wave(tuple([round(dc)] * WAVE_SAMPLES))

    real = [0.0] * WAVE_SAMPLES
    for h in harmonics:
        if len(h) == 2:
            k, amp = h
            phase = 0.0
        else:
            k, amp, phase = h
        if k <= 0 or k > NYQUIST_BIN:
            raise ValueError(
                f"harmonic bin {k} out of range (1..{NYQUIST_BIN})"
            )
        p = math.radians(phase)
        for n in range(WAVE_SAMPLES):
            real[n] += amp * math.sin(2 * math.pi * k * n / WAVE_SAMPLES + p)

    lo, hi = min(real), max(real)
    span = hi - lo or 1.0
    samples = tuple(
        max(0, min(WAVE_MAX, round((x - lo) / span * WAVE_MAX)))
        for x in real
    )
    return Wave(samples)


def _canonicalize_interval(name: str) -> str:
    key = _INTERVAL_ALIASES.get(name.lower(), name)
    if key not in INTERVAL_RATIOS:
        raise ValueError(
            f"unknown interval {name!r}. "
            f"Known: {sorted(INTERVAL_RATIOS)} (aliases: {sorted(_INTERVAL_ALIASES)})"
        )
    return key


def interval_wave(interval: str) -> Wave:
    """Build a FADE-style two-partial adjacent-bin dyad wave.

    Only accepts the four adjacent-bin intervals that reliably read as two
    distinct pitches on the wave channel:

      'm3' → bins 5:6  (ratio 6/5)
      'M3' → bins 4:5  (ratio 5/4)
      'P4' → bins 3:4  (ratio 4/3)
      'P5' → bins 2:3  (ratio 3/2)

    These are FADE's original set plus 'P5' (bins 2:3, also seen in
    Microplastics' "Sine wave" bank slot). Wider ratios don't survive
    perceptually on 32 samples × 4 bits — they collapse into a single
    colored timbre. Use `from_harmonics()` for those.
    """
    key = _canonicalize_interval(interval)
    num, den = INTERVAL_RATIOS[key]        # e.g. m3 → (6, 5)
    return from_harmonics([(den, 1.0), (num, 1.0)])


# --------------------------------------------------------------------------- #
# Convenience for the Song container                                          #
# --------------------------------------------------------------------------- #

def wave_from_song_bank(song, index: int) -> Wave:
    """Extract wave `index` from a Song and return as a Wave object.

    The Song.waves list stores raw `bytes` (32 nibble-per-byte); this wraps
    them for analysis without mutating the Song.
    """
    return Wave.from_bytes(song.waves[index])


__all__ = [
    "Wave",
    "WaveReport",
    "PeakBin",
    "DetectedInterval",
    "analyze",
    "from_harmonics",
    "interval_wave",
    "wave_from_song_bank",
    "INTERVAL_RATIOS",
    "WAVE_SAMPLES",
    "WAVE_MAX",
    "NYQUIST_BIN",
]
