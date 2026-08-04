"""Named wave presets for wave-channel timbre experimentation.

REORGANIZED 2026-08-04 after listening tests. Categories:

    F1. Reinforced dyads — codified octave-doubled-dyad recipe (the design
        pattern reverse-engineered from FADE's Microplastics waves).
        Ears-confirmed: sounds cleaner than FADE's own hand-shaped waves.
    F2. Extended dyads — adjacent-bin dyads outside the classic
        m3/M3/P4/P5 set. Ears-verdict: tinny colors, not clear dyads —
        kept as color reference material, not promoted to interval_wave().
    A-D (legacy). Multi-bin harmonic-series designs originally pitched as
        chord-flavored (dom7/maj7/min7/dim7). Ears confirmed no chord
        percept; retained as "colored bright tones" reference. All chord
        claims stripped.
    E. Register shifters — coprime/all-even-bin designs that shift the
        perceived fundamental via missing-fundamental illusion.
    F. P8 octave doubler.
    G. Formant / vowel clusters — three-adjacent-bin narrow bands.
        Ears-confirmed favorite: formant-mid.
    H. Inharmonic metallic — coprime-prime clusters. Jameson-confirmed
        strongest of the non-dyad exploratory categories.

FADE's own waves were investigated as a reference and found to be
hand-shaped (not formulaic). NOT shipped as presets to avoid republishing
someone else's specific artistic waves. The codified F1 recipe captures
their design principle and Jameson's ears prefer F1 to the FADE originals.

See NOTES.md for the theory and the listening-test log.
"""

from __future__ import annotations

from .waves import (
    Wave,
    from_harmonics,
    interval_wave,
    interval_wave_reinforced,
)


# --------------------------------------------------------------------------- #
# Category F1: Reinforced dyads (highest confidence)                          #
# --------------------------------------------------------------------------- #
# Adjacent-bin dyad + octave-doubled dyad at 30% amplitude. Codified version
# of the design pattern reverse-engineered from FADE's minor/major/fourth.
# Ears-confirmed 2026-08-04: sounds cleaner than FADE's hand-shaped versions.
#
# Naming convention: REINFORCED_MIN3 = minor third (5:6), REINFORCED_MAJ3 =
# major third (4:5), REINFORCED_P4 = perfect fourth (3:4). "MIN"/"MAJ" prefix
# avoids the m/M lowercase/uppercase collision in Python constant names.
#
# Note: REINFORCED_P5 was tried and cut — bins 2:3 + 4:6 approximates a
# natural harmonic series 2:3:4:6 that reads as saw-ish rather than a clear
# P5 dyad. Use plain interval_wave("P5") if you want a P5.

REINFORCED_MIN3: Wave = interval_wave_reinforced("m3")
"""Bins 5:6 (m3 dyad) + 10:12 (octave-doubled dyad) at 30% weight.
Ears-confirmed as a clean minor-third dyad, cleaner than the FADE original."""

REINFORCED_MAJ3: Wave = interval_wave_reinforced("M3")
"""Bins 4:5 (M3 dyad) + 8:10 (octave-doubled dyad) at 30% weight.
Ears-confirmed as a clean major-third dyad."""

REINFORCED_P4: Wave = interval_wave_reinforced("P4")
"""Bins 3:4 (P4 dyad) + 6:8 (octave-doubled dyad) at 30% weight.
Ears-confirmed as a clean perfect-fourth dyad."""


# --------------------------------------------------------------------------- #
# Category F2: Extended adjacent-bin dyads (tinny colors, not clear dyads)    #
# --------------------------------------------------------------------------- #
# Adjacent-bin dyads beyond m3/M3/P4/P5. The adjacency rule predicted these
# should read as clear dyads; ears confirmed 2026-08-04 they do NOT — they
# sound tinny/interesting rather than distinctly two-pitched. Kept as color
# reference material. Not promoted to interval_wave().

DYAD_6_7: Wave = from_harmonics([(6, 1.0), (7, 1.0)])
"""Bins 6:7 (septimal m3 ratio 7:6). Tinny color, not a clear m3 dyad."""

DYAD_7_8: Wave = from_harmonics([(7, 1.0), (8, 1.0)])
"""Bins 7:8 (septimal M2 ratio 8:7). Tinny color."""

DYAD_8_9: Wave = from_harmonics([(8, 1.0), (9, 1.0)])
"""Bins 8:9 (whole tone ratio 9:8). Tinny color, doesn't read as a clear
whole-tone dyad — likely too high in register for the adjacency rule to
save the dyad from fusion."""

DYAD_9_10: Wave = from_harmonics([(9, 1.0), (10, 1.0)])
"""Bins 9:10 (minor whole tone ratio 10:9). Tinny color."""

DYAD_10_11: Wave = from_harmonics([(10, 1.0), (11, 1.0)])
"""Bins 10:11 (undecimal neutral second ratio 11:10). Tinny color."""


# --------------------------------------------------------------------------- #
# Category A (legacy, retained): natural-harmonic-series 4-bin designs        #
# --------------------------------------------------------------------------- #
# Originally shipped as "dom7 flavor" — ears confirmed the chord percept
# doesn't survive fusion. Retained as bright-single-tone reference material.
# ALL chord-flavor claims stripped from docstrings.

DOM7_NARROW: Wave = from_harmonics([(4, 1.0), (5, 1.0), (6, 1.0), (7, 1.0)])
"""Bins 4:5:6:7, equal amplitudes. GCD=1 → tracker-note pitch. Four
adjacent low-mid partials in the natural harmonic series through the
seventh. Reads as one colored bright tone, brass-flavored. No chord
percept (listening test confirmed)."""

DOM7_WIDE: Wave = from_harmonics([(8, 1.0), (10, 1.0), (12, 1.0), (14, 1.0)])
"""Bins 8:10:12:14, equal amplitudes. GCD=2 → pitch = one octave above
tracker note. Same harmonic ratios as DOM7_NARROW but perceived an
octave higher. Thinner, brighter version of the same color."""

DOM7_ROLLOFF: Wave = from_harmonics([(4, 1/4), (5, 1/5), (6, 1/6), (7, 1/7)])
"""Bins 4:5:6:7 with 1/n amplitude decay. Softer, more voice-like
version of DOM7_NARROW."""


# --------------------------------------------------------------------------- #
# Category B (legacy, retained): high-partial designs                         #
# --------------------------------------------------------------------------- #
# Originally shipped as "maj7 timbres" — ears confirmed as WORST of A-D,
# because bin 15 sits far from the triad body and gets fully fused. Kept
# as bright-shimmer reference. No chord claims.

MAJ7_JUST: Wave = from_harmonics([(8, 1.0), (10, 1.0), (12, 1.0), (15, 1.0)])
"""Bins 8:10:12:15, equal amplitudes. GCD=1. High shimmer / bright tone
with an aggressive top-end partial. Confirmed NOT a maj7 percept."""

MAJ7_LEADINGTONE_HINT: Wave = from_harmonics(
    [(8, 1.0), (10, 1.0), (12, 1.0), (15, 0.4)]
)
"""Same bins as MAJ7_JUST with bin 15 at 40% amplitude. Softer version
of the same shimmer."""

MAJ7_OPEN: Wave = from_harmonics([(4, 1.0), (5, 1.0), (6, 1.0), (15, 0.6)])
"""Bins 4:5:6 (triad-body harmonics) + bin 15 (halo two octaves higher)
at 60%. GCD=1. Widest-spread design in the legacy set; worst listener
match to any chord percept."""


# --------------------------------------------------------------------------- #
# Category C (legacy, retained): minor-flavored 3-4 bin designs               #
# --------------------------------------------------------------------------- #
# Originally shipped as "min7 experiments." Retained without chord claims.

MIN7_TRUNCATED: Wave = from_harmonics([(10, 1.0), (12, 1.0), (15, 1.0)])
"""Bins 10:12:15 — JI minor triad ratios in the upper register. GCD=1.
Reads as a bright single tone with narrow-cluster character."""

MIN7_SEPTIMAL: Wave = from_harmonics([(6, 1.0), (7, 1.0), (9, 1.0), (11, 1.0)])
"""Bins 6:7:9:11. GCD=1. Septimal + 11-limit cluster. Reads as a warmer,
noticeably inharmonic single pitch."""

MIN7_COMPRESSED: Wave = from_harmonics([(5, 1.0), (6, 1.0), (7, 1.0), (9, 1.0)])
"""Bins 5:6:7:9. GCD=1. Tight low-harmonic cluster. Bin 5:6 dyad drives
an m3-ish impression under a rougher upper edge."""


# --------------------------------------------------------------------------- #
# Category D (legacy, retained): consecutive-bin cluster                      #
# --------------------------------------------------------------------------- #

DIM7_SEPTIMAL: Wave = from_harmonics([(5, 1.0), (6, 1.0), (7, 1.0), (8, 1.0)])
"""Bins 5:6:7:8 — consecutive septimal-m3 stack. GCD=1. Dense unstable
timbre with bell-like tension."""


# --------------------------------------------------------------------------- #
# Category E: register shifters                                               #
# --------------------------------------------------------------------------- #

OCTAVE_UP_SINE: Wave = from_harmonics([(2, 1.0)])
"""Bin 2 only. GCD=2 → pure sine one octave above tracker note. Cheapest
possible register shifter."""

THICKENER: Wave = from_harmonics([(2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0)])
"""Bins 2:3:4:5, no bin 1 energy. GCD=1 → phantom root at tracker note
via missing-fundamental illusion. Adds harmonic warmth; may bias
slightly brighter than a wave with real bin-1 energy."""


# --------------------------------------------------------------------------- #
# Category F: P8 fused octave doubler                                         #
# --------------------------------------------------------------------------- #

P8: Wave = from_harmonics([(1, 1.0), (2, 1.0)])
"""Bins 1:2, equal amplitudes. Fused octave-doubled tracker note.
Precedent: FADE's Bank 9 'Pointy' has the same bin content."""


# --------------------------------------------------------------------------- #
# Category G: formant / vowel clusters                                        #
# --------------------------------------------------------------------------- #
# Ears confirmed: formant-mid is the strongest 'formant' character.

FORMANT_LOW: Wave = from_harmonics([(6, 1.0), (7, 1.0), (8, 1.0)])
"""Bins 6:7:8. Three-adjacent-bin cluster, mid-register. GCD=1. Hollow,
reedy vowel-like color."""

FORMANT_MID: Wave = from_harmonics([(7, 1.0), (8, 1.0), (9, 1.0)])
"""Bins 7:8:9. GCD=1. Brighter, more nasal than FORMANT_LOW.
Ears-confirmed as the most 'formant'-sounding of the set."""

FORMANT_HIGH: Wave = from_harmonics([(8, 1.0), (9, 1.0), (10, 1.0)])
"""Bins 8:9:10. GCD=1. Distinctly nasal high-formant color."""

FORMANT_LOW_ROLLOFF: Wave = from_harmonics([(6, 1.0), (7, 1/2), (8, 1/3)])
"""Bins 6:7:8 with amplitude decay. Softer edge on the cluster."""


# --------------------------------------------------------------------------- #
# Category H: inharmonic metallic (ears-confirmed STRONGEST category)         #
# --------------------------------------------------------------------------- #
# Ears confirmed this as the most productive exploratory category. No
# specific ratio stood out from the initial three, so more coprime-prime
# variants ship here for exploration.

METALLIC_7_11_13: Wave = from_harmonics([(7, 1.0), (11, 1.0), (13, 1.0)])
"""Bins 7:11:13. Three coprime primes, high-anchored. GCD=1. Bell-like."""

METALLIC_5_7_11: Wave = from_harmonics([(5, 1.0), (7, 1.0), (11, 1.0)])
"""Bins 5:7:11. Three coprime primes, warmer low end. GCD=1."""

METALLIC_3_7_11: Wave = from_harmonics([(3, 1.0), (7, 1.0), (11, 1.0)])
"""Bins 3:7:11. Anchored low; more fundamental presence."""


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #

PRESETS: dict[str, Wave] = {
    # F1: Reinforced dyads
    "reinforced-m3":         REINFORCED_MIN3,
    "reinforced-M3":         REINFORCED_MAJ3,
    "reinforced-P4":         REINFORCED_P4,
    # F2: Extended dyads
    "dyad-6-7":              DYAD_6_7,
    "dyad-7-8":              DYAD_7_8,
    "dyad-8-9":              DYAD_8_9,
    "dyad-9-10":             DYAD_9_10,
    "dyad-10-11":            DYAD_10_11,
    # A (legacy)
    "dom7-narrow":           DOM7_NARROW,
    "dom7-wide":             DOM7_WIDE,
    "dom7-rolloff":          DOM7_ROLLOFF,
    # B (legacy)
    "maj7-just":             MAJ7_JUST,
    "maj7-leadingtone-hint": MAJ7_LEADINGTONE_HINT,
    "maj7-open":             MAJ7_OPEN,
    # C (legacy)
    "min7-truncated":        MIN7_TRUNCATED,
    "min7-septimal":         MIN7_SEPTIMAL,
    "min7-compressed":       MIN7_COMPRESSED,
    # D (legacy)
    "dim7-septimal":         DIM7_SEPTIMAL,
    # E
    "octave-up-sine":        OCTAVE_UP_SINE,
    "thickener":             THICKENER,
    # F
    "p8":                    P8,
    # G
    "formant-low":           FORMANT_LOW,
    "formant-mid":           FORMANT_MID,
    "formant-high":          FORMANT_HIGH,
    "formant-low-rolloff":   FORMANT_LOW_ROLLOFF,
    # H
    "metallic-7-11-13":      METALLIC_7_11_13,
    "metallic-5-7-11":       METALLIC_5_7_11,
    "metallic-3-7-11":       METALLIC_3_7_11,
}


PRESET_CATEGORIES: dict[str, list[str]] = {
    "F1: Reinforced dyads (ears-confirmed, ship-ready)": [
        "reinforced-m3", "reinforced-M3", "reinforced-P4",
    ],
    "F2: Extended adjacent-bin dyads (tinny colors, not clear dyads)": [
        "dyad-6-7", "dyad-7-8", "dyad-8-9", "dyad-9-10", "dyad-10-11",
    ],
    "A (legacy): bright colored tones — no chord percept": [
        "dom7-narrow", "dom7-wide", "dom7-rolloff",
    ],
    "B (legacy): high-shimmer tones — no chord percept": [
        "maj7-just", "maj7-leadingtone-hint", "maj7-open",
    ],
    "C (legacy): low-cluster tones — no chord percept": [
        "min7-truncated", "min7-septimal", "min7-compressed",
    ],
    "D (legacy): consecutive-bin cluster — no chord percept": [
        "dim7-septimal",
    ],
    "E: register shifters": [
        "octave-up-sine", "thickener",
    ],
    "F: P8 octave doubler": [
        "p8",
    ],
    "G: formant / vowel clusters": [
        "formant-low", "formant-mid", "formant-high", "formant-low-rolloff",
    ],
    "H: inharmonic metallic (strongest exploratory category)": [
        "metallic-7-11-13", "metallic-5-7-11", "metallic-3-7-11",
    ],
}


__all__ = [
    "PRESETS",
    "PRESET_CATEGORIES",
    # F1
    "REINFORCED_MIN3", "REINFORCED_MAJ3", "REINFORCED_P4",
    # F2
    "DYAD_6_7", "DYAD_7_8", "DYAD_8_9", "DYAD_9_10", "DYAD_10_11",
    # A/B/C/D legacy
    "DOM7_NARROW", "DOM7_WIDE", "DOM7_ROLLOFF",
    "MAJ7_JUST", "MAJ7_LEADINGTONE_HINT", "MAJ7_OPEN",
    "MIN7_TRUNCATED", "MIN7_SEPTIMAL", "MIN7_COMPRESSED",
    "DIM7_SEPTIMAL",
    # E/F/G/H
    "OCTAVE_UP_SINE", "THICKENER",
    "P8",
    "FORMANT_LOW", "FORMANT_MID", "FORMANT_HIGH", "FORMANT_LOW_ROLLOFF",
    "METALLIC_7_11_13", "METALLIC_5_7_11", "METALLIC_3_7_11",
]
