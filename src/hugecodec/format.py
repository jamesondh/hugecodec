"""In-memory representation of a hUGETracker song.

The dataclasses below are the *canonical* in-memory form. On read we parse each
version's on-disk layout into these dataclasses, filling in defaults for fields
introduced in later versions. This deliberately loses no user data — anything
present on disk is preserved — but does normalize the shape so downstream code
doesn't have to case-split on version.

Sentinel values for empty cell fields come from hUGETracker's own conventions
(see `src/constants.pas` in the tracker repo). Values are as commonly observed
in real files; we'll verify against a controlled write in the writer phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# --------------------------------------------------------------------------- #
# Sentinel / empty values for cells                                           #
# --------------------------------------------------------------------------- #

NOTE_EMPTY = 90          # NO_NOTE per hUGETracker constants.pas:141
NOTE_OFF = 91            # note-off marker (TODO: verify against tracker source)
INSTRUMENT_EMPTY = 0     # 0 = no instrument change
VOLUME_EMPTY = 0         # V6+ only; 0 = no volume change on this cell
EFFECT_EMPTY = 0         # 0 with param 0 = no effect

# Subpattern note-field encoding. In an instrument's subpattern the `note`
# field is a SIGNED OFFSET expressed as MIDDLE_NOTE + delta. Constants
# from hUGETracker/src/constants.pas (HIGHEST_NOTE=71, LOWEST_NOTE=0,
# MIDDLE_NOTE=(71-0)/2+1 = 36). See EFFECTS.md § "Offset encoding".
MIDDLE_NOTE = 36
LOWEST_NOTE = 0
HIGHEST_NOTE = 71

# Instrument type enum (matches Pascal TInstrumentType)
INSTR_SQUARE: Literal[0] = 0
INSTR_WAVE: Literal[1] = 1
INSTR_NOISE: Literal[2] = 2

INSTR_TYPE_NAMES = {0: "square", 1: "wave", 2: "noise"}


# --------------------------------------------------------------------------- #
# Cell / Pattern                                                              #
# --------------------------------------------------------------------------- #

@dataclass
class Cell:
    note: int = NOTE_EMPTY
    instrument: int = INSTRUMENT_EMPTY
    volume: int = VOLUME_EMPTY          # V6+ only; 0 on older versions
    effect_code: int = EFFECT_EMPTY
    effect_params: int = 0              # raw byte 0x00..0xFF

    @property
    def has_note(self) -> bool:
        return self.note != NOTE_EMPTY and self.note != NOTE_OFF

    @property
    def has_effect(self) -> bool:
        return self.effect_code != 0 or self.effect_params != 0

    def effect_str(self) -> str:
        """Return the effect as e.g. 'F03' or '.' for empty."""
        if not self.has_effect:
            return "."
        return f"{self.effect_code:X}{self.effect_params:02X}"


@dataclass
class Pattern:
    """A pattern is 64 rows, one per row index."""
    cells: list[Cell] = field(default_factory=lambda: [Cell() for _ in range(64)])

    def __post_init__(self):
        if len(self.cells) != 64:
            raise ValueError(f"pattern must have 64 rows, got {len(self.cells)}")


# --------------------------------------------------------------------------- #
# Instrument                                                                  #
# --------------------------------------------------------------------------- #

@dataclass
class Instrument:
    """Canonical instrument shape (superset across V1–V7).

    Fields not present in older versions are filled with their defaults. When
    the writer arrives, we'll pick the on-disk version based on which fields
    diverge from defaults (or the user's explicit choice).
    """
    type: int = INSTR_SQUARE     # TInstrumentType
    name: str = ""

    # Length / envelope
    length: int = 0
    length_enabled: bool = False
    initial_volume: int = 0       # 0..15
    vol_sweep_direction: int = 0  # 0=up, 1=down
    vol_sweep_amount: int = 0     # 0..7

    # Square-only sweep (NR10)
    sweep_time: int = 0
    sweep_inc_dec: int = 0        # 0=up, 1=down
    sweep_shift: int = 0

    # Square: duty (NR11)
    duty: int = 0                 # 0..3

    # Wave-only
    output_level: int = 0
    waveform: int = 0             # index into wave bank

    # Noise-only
    shift_clock_freq: int = 0     # V1–V5 only; removed in V6+
    counter_step: int = 0         # 0=15-bit, 1=7-bit
    dividing_ratio: int = 0       # V1–V5 only; removed in V6+ (folded into subpattern)

    # V4/V5 only — noise macro (6 signed bytes, values in -31..32)
    noise_macro: tuple[int, ...] = (0, 0, 0, 0, 0, 0)

    # V6+ only
    subpattern_enabled: bool = False
    subpattern: Pattern | None = None

    @property
    def type_name(self) -> str:
        return INSTR_TYPE_NAMES.get(self.type, f"unknown({self.type})")


# --------------------------------------------------------------------------- #
# Song                                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class Song:
    """Canonical in-memory song.

    `source_version` records the on-disk version we parsed from, so callers
    can reason about which fields are meaningful. The writer will use it as
    the default target version.
    """
    source_version: int = 7

    name: str = ""
    artist: str = ""
    comment: str = ""

    # Instruments. V3+ split into three banks of 15; older versions have a
    # single flat bank of 15. We always store the same shape here:
    #   duty[1..15], wave[1..15], noise[1..15]  (indices 1-based to match Pascal)
    # For V1/V2 songs where there's only one flat bank, we distribute by the
    # instrument's own Type_ field into the appropriate bank and leave the
    # unused slots as defaults. Slot 0 of each list is unused (Pascal 1..15).
    duty_instruments: list[Instrument] = field(default_factory=lambda: [Instrument() for _ in range(16)])
    wave_instruments: list[Instrument] = field(default_factory=lambda: [Instrument() for _ in range(16)])
    noise_instruments: list[Instrument] = field(default_factory=lambda: [Instrument() for _ in range(16)])

    # 16 waves, each 32 4-bit samples packed as 32 bytes (V3+) or 33 bytes (V1/V2).
    # We normalize to 32; the V1/V2 vestigial 33rd byte is captured in
    # `_v1_wave_trailer` for round-trip fidelity if we ever care.
    waves: list[bytes] = field(default_factory=lambda: [bytes(32) for _ in range(16)])
    _v1_wave_trailer: list[int] | None = None  # only set for V1/V2 files

    # Speed. V1–V6: single int (used for all channels). V7: per-channel.
    ticks_per_row: list[int] = field(default_factory=lambda: [7, 7, 7, 7])

    # V6+ only
    timer_enabled: bool = False
    timer_divider: int = 0

    # Patterns: sparse key -> Pattern
    patterns: dict[int, Pattern] = field(default_factory=dict)

    # OrderMatrix: 4 channels × variable-length list of pattern keys
    order_matrix: list[list[int]] = field(default_factory=lambda: [[], [], [], []])

    # Routines: 16 slots (V2+); empty strings for V1
    routines: list[str] = field(default_factory=lambda: ["" for _ in range(16)])

    # --- convenience --------------------------------------------------------

    @property
    def all_instruments(self) -> list[Instrument]:
        """Flat 45-length list matching Pascal's `All` variant view."""
        return self.duty_instruments[1:] + self.wave_instruments[1:] + self.noise_instruments[1:]

    def instrument_for_channel(self, channel: int, slot: int) -> Instrument | None:
        """Look up the instrument played by (channel, slot).

        channel: 0=CH1, 1=CH2, 2=CH3, 3=CH4.
        slot: 1..15 (0 = no instrument).
        Returns None for slot 0.
        """
        if slot < 1 or slot > 15:
            return None
        if channel in (0, 1):
            return self.duty_instruments[slot]
        if channel == 2:
            return self.wave_instruments[slot]
        if channel == 3:
            return self.noise_instruments[slot]
        raise ValueError(f"channel must be 0..3, got {channel}")

    def order_count(self) -> int:
        """Max order length across the 4 channels. Mirrors Pascal OrderCount."""
        return max((len(ch) for ch in self.order_matrix), default=0)

    # --- order-matrix trailer handling -------------------------------------

    def playable_orders(self, channel: int) -> list[int]:
        """Return the *playable* orders for a channel — i.e. all on-disk
        entries except the final trailer slot.

        hUGETracker's on-disk `OrderMatrix[ch]` = `playable_orders + [trailer]`.
        The trailer is a UI buffer never displayed or played; see
        `NOTES.md` § "OrderMatrix trailer" for the source cross-reference.

        Returns an empty list if the channel array is empty (no trailer, no
        orders — degenerate file).
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError(f"channel must be 0..3, got {channel}")
        orders = self.order_matrix[channel]
        return list(orders[:-1]) if orders else []

    def set_playable_orders(self, channel: int, orders: list[int], *,
                            trailer: int = 0) -> None:
        """Set the playable orders for a channel; the trailer slot is
        appended automatically.

        Use this instead of assigning to `song.order_matrix[ch]` directly.
        The raw `order_matrix` field is length-of-on-disk (playable + 1);
        losing the trailer causes hUGETracker to open the song with an empty
        order grid, which silently falls back to Pattern[0] on every channel.
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError(f"channel must be 0..3, got {channel}")
        self.order_matrix[channel] = list(orders) + [trailer]
