"""Constructors for common hUGETracker subpattern shapes.

A subpattern is a mini-tracker grid attached to an instrument (V6+ format).
Each subpattern row runs on **one tick** of the outer pattern row. See
`EFFECTS.md` § "Subpatterns" for the encoding details and the corpus
shape catalog that informed these constructors.

## Note-field encoding

In subpatterns, the `note` field is `MIDDLE_NOTE + delta_semitones` where
`MIDDLE_NOTE = 36`. So:

  offset(0)   → note field 36  (base note, no change)
  offset(+12) → note field 48  (octave up)
  offset(-7)  → note field 29  (perfect fifth down)

An empty note (`NOTE_EMPTY = 90`) means "hold the current pitch offset
from the previous non-empty row." It does NOT mean "silence."

## Loop semantics (compiled subpattern length = 32 rows)

Confirmed against `hUGETracker/src/codegen.pas:475-528`: only the first
**32 rows** of the 64-row `TPattern` buffer are compiled into the ROM.
Row 0 plays once on note-trigger; rows 1..31 are the loop body.

The `Volume` field of a subpattern cell is repurposed as the **jump
target**:

- `volume = 0` → advance to the next row normally
- `volume = N` (1..31) → jump to row N after this cell plays
- If row 31 has `volume = 0`, the codegen automatically inserts a
  jump-to-row-1 so subpatterns loop by default

The corpus shows two loop patterns:
- **Cycle**: put an explicit `volume = <loop_start>` on the last used row
  to jump back and tighten the loop (avoids the 29-empty-rows dead
  zone before the auto-jump fires). e.g. FADE Microplastics *arp1*:
  6 rows, volume=1 on row 5.
- **Halt**: put `volume = self_row` on a row to freeze there. Useful for
  one-shot shapes (kick, pluck) that shouldn't retrigger. e.g. Kekri
  *basso*: volume=9 on row 9.

## What each constructor returns

Each function returns a fully-populated 64-row `Pattern` object ready to
drop into `instrument.subpattern` after also setting
`instrument.subpattern_enabled = True`. Rows past the shape's used length
are left empty (`Cell()`). Constructors that need to loop set the
appropriate jump target themselves.

## Example

    from hugecodec import Instrument
    from hugecodec.subpatterns import kick_transient

    inst = Instrument(type=INSTR_NOISE, name="kick")
    inst.initial_volume = 15
    inst.vol_sweep_direction = 1  # down
    inst.vol_sweep_amount = 5
    inst.subpattern_enabled = True
    inst.subpattern = kick_transient(drop_semitones=24, transient_ticks=2)
"""

from __future__ import annotations

from .format import (
    Cell,
    Pattern,
    MIDDLE_NOTE,
    LOWEST_NOTE,
    HIGHEST_NOTE,
    NOTE_EMPTY,
)


__all__ = [
    "offset",
    "pluck",
    "kick_transient",
    "hat_flat",
    "arp_cycle",
    "vibrato_ramp",
    "duty_morph",
    "envelope_steps",
    "empty",
]


# --------------------------------------------------------------------------- #
# Low-level helpers                                                           #
# --------------------------------------------------------------------------- #

def offset(semitones: int) -> int:
    """Convert a semitone offset (positive or negative) into a subpattern
    note-field value. Clamps to the valid encoding range (-36 .. +35)."""
    encoded = MIDDLE_NOTE + semitones
    if encoded < LOWEST_NOTE:
        return LOWEST_NOTE
    if encoded > HIGHEST_NOTE:
        return HIGHEST_NOTE
    return encoded


def _blank_pattern() -> Pattern:
    return Pattern()


def _place(pattern: Pattern, row: int, *,
           note_offset: int | None = None,
           effect_code: int = 0,
           effect_params: int = 0,
           jump_to: int = 0) -> None:
    """Set a single cell in a subpattern.

    `note_offset` is in semitones (converted through `offset()`). None means
    leave the note field empty (holds previous offset).

    `jump_to` writes to the `Volume` field, which the tracker reads as the
    jump target (0 = advance, N = jump to row N). See module docstring for
    loop semantics.
    """
    if row >= 32:
        raise ValueError(f"subpattern row {row} beyond compiled length 32")
    cell = pattern.cells[row]
    cell.note = offset(note_offset) if note_offset is not None else NOTE_EMPTY
    cell.effect_code = effect_code
    cell.effect_params = effect_params
    cell.volume = jump_to


# --------------------------------------------------------------------------- #
# Shape constructors                                                          #
# --------------------------------------------------------------------------- #

def empty() -> Pattern:
    """Empty enabled subpattern. Useful as a starting point for hand-editing."""
    return _blank_pattern()


def pluck(octave_offset: int = 12) -> Pattern:
    """Percussive pluck: one row at `+octave_offset` semitones, then base.

    Corpus example: FADE Microplastics *bass* uses `[+12, +00]` with all
    volumes zero. The tick-0 octave-up hit reads as attack; tick-1 onward
    is the sustained pitch. Row 1 has a jump-to-self so the pluck doesn't
    accidentally re-trigger via the row-31 auto-jump — this keeps the note
    at base pitch until the instrument envelope silences it.
    """
    p = _blank_pattern()
    _place(p, 0, note_offset=octave_offset)
    _place(p, 1, note_offset=0, jump_to=1)  # halt at row 1
    return p


def kick_transient(*, drop_semitones: int = 24,
                   transient_ticks: int = 2,
                   body_ticks: int = 4) -> Pattern:
    """Kick-drum-style transient for CH4 (noise channel).

    First `transient_ticks` rows sit at +`drop_semitones` (high, punchy),
    then drop to base offset for `body_ticks` rows. The last body row
    halts (jump-to-self) so the transient doesn't re-fire via the row-31
    auto-loop. The instrument's volume envelope handles the decay.

    Corpus reference: FADE Microplastics *snare* uses `[+00, -36, -36, +00]`
    (extreme negative offset for sub-transient LFSR crackle). The classic
    kick shape flips this — start high, drop to base — which is what this
    constructor produces.
    """
    p = _blank_pattern()
    for i in range(transient_ticks):
        _place(p, i, note_offset=drop_semitones)
    last_body_row = transient_ticks + body_ticks - 1
    for i in range(body_ticks):
        row = transient_ticks + i
        jump = row if row == last_body_row else 0    # halt on the last body row
        _place(p, row, note_offset=0, jump_to=jump)
    return p


def hat_flat(rows: int = 6, *, halt: bool = True) -> Pattern:
    """Constant-offset subpattern used for hi-hats.

    Corpus reference: FADE Strap *hat1* and *hat2* both use 6-row `[+00]`
    subpatterns — the character comes entirely from the noise instrument's
    envelope and the played note's LFSR pitch.

    When `halt=True` (default), the last row jumps to itself so the hat
    doesn't re-trigger via the row-31 auto-loop. Set `halt=False` for a
    hat that ticks continuously as long as the outer note is held.
    """
    p = _blank_pattern()
    for i in range(rows):
        jump = i if (halt and i == rows - 1) else 0
        _place(p, i, note_offset=0, jump_to=jump)
    return p


def arp_cycle(intervals: list[int], *, ticks_per_step: int = 1) -> Pattern:
    """Broken-chord arpeggio cycled per tick.

    `intervals` is a list of semitone offsets from the base note. The
    layout is:

        row 0:               +0 (trigger — always start on the base note)
        rows 1..:            intervals[0] held for `ticks_per_step` rows
        next block:          intervals[1] held for `ticks_per_step` rows
        ...
        last row of block N: intervals[N-1] with jump-to-row-1

    Row 0 exists so that the note-on hears the base pitch; rows 1..end
    are the sustained loop body. Because the loop jumps back to row 1
    (not row 0), the trigger's `+0` only plays once — this is what you
    want if `intervals` already includes `0`, since the loop will hit
    that offset naturally each cycle.

    Corpus reference: FADE Microplastics *arp1* uses
    `[+8, +17, +00, +20, +5, +12]` with a jump-to-row-1 on the last row.

    `ticks_per_step=1` gives a very fast arp (one note per tick —
    audibly a click-train at typical tempos). For a slower / more
    audible arp on a held chord, use `ticks_per_step=3` or `4`.

    Prefer this over the `0xy` effect for anything longer than a single
    row — subpattern arps are trivially sustained across held notes,
    while `0xy` needs re-entry on every main pattern row.
    """
    if not intervals:
        raise ValueError("arp_cycle requires at least one interval")
    if ticks_per_step < 1:
        raise ValueError("ticks_per_step must be >= 1")
    p = _blank_pattern()
    # Row 0: base note trigger. Explicit +0 so the first note-on doesn't
    # inherit an ambiguous prior offset from whatever was played before.
    _place(p, 0, note_offset=0)

    body_rows = min(31, len(intervals) * ticks_per_step)
    row = 1
    for i, semi in enumerate(intervals):
        for step in range(ticks_per_step):
            if row > body_rows:
                break
            note_off = semi if step == 0 else None
            # Jump back to row 1 on the last body row → tight loop over
            # rows 1..body_rows. Row 0's trigger `+0` doesn't recur, but
            # if `0` is in `intervals` the loop hits it on schedule.
            jump = 1 if row == body_rows else 0
            _place(p, row, note_offset=note_off, jump_to=jump)
            row += 1
        if row > body_rows:
            break
    return p


def vibrato_ramp(depths: list[int], *, speed: int = 4,
                 hold_ticks_per_step: int = 1) -> Pattern:
    """Vibrato that ramps depth over time using `4xy` on consecutive rows.

    `depths` is a list of vibrato depths (0..15); each depth is held for
    `hold_ticks_per_step` subpattern rows. `speed` is the `x` nibble of the
    `4xy` effect (higher = slower switching).

    The last row halts (jump-to-self) so the ramp holds at max depth
    once reached, rather than looping back to the beginning.

    Corpus data: top vibrato params include `4C3`, `472`, `443`, `442`.
    """
    if not depths:
        raise ValueError("vibrato_ramp requires at least one depth")
    if not (0 <= speed <= 0xF):
        raise ValueError(f"speed must be 0..15, got {speed}")
    p = _blank_pattern()
    total_rows = min(32, len(depths) * hold_ticks_per_step)
    row = 0
    for depth in depths:
        if not (0 <= depth <= 0xF):
            raise ValueError(f"depth must be 0..15, got {depth}")
        params = (speed << 4) | depth
        for _ in range(hold_ticks_per_step):
            if row >= 32:
                return p
            jump = row if row == total_rows - 1 else 0
            _place(p, row, effect_code=0x4, effect_params=params, jump_to=jump)
            row += 1
    return p


# Duty position → NR11 byte value (top 2 bits = duty, low 6 = length).
_DUTY_TO_NR11 = {0: 0x00, 1: 0x40, 2: 0x80, 3: 0xC0}


def duty_morph(duty_sequence: list[int], *, ticks_per_step: int = 1,
               loop: bool = True) -> Pattern:
    """Cycle through duty cycles on CH1/CH2 using `9xx`.

    `duty_sequence` is a list of duty positions (0=12.5%, 1=25%, 2=50%,
    3=75%). Each position is held for `ticks_per_step` subpattern rows.

    When `loop=True` (default), the last row jumps to row 1 so the morph
    cycles continuously. Row 0 plays only on trigger. Set `loop=False` for
    a one-shot morph that halts at the final duty.

    Corpus reference: Coffee Bat *Wyrmhole* and Tempest *Kekri* use `9xx`
    heavily in duty-morph subpatterns. Main-pattern top params: `940`,
    `980`, `900`, `9C0` — the four canonical duty positions.

    Only valid on CH1/CH2 duty instruments. On CH3 `9xx` swaps the wave
    (and restarts the note); on CH4 it changes LFSR width (dangerous).
    """
    if not duty_sequence:
        raise ValueError("duty_morph requires at least one duty position")
    p = _blank_pattern()
    total_rows = min(32, len(duty_sequence) * ticks_per_step)
    row = 0
    for duty in duty_sequence:
        if duty not in _DUTY_TO_NR11:
            raise ValueError(f"duty must be 0..3, got {duty}")
        params = _DUTY_TO_NR11[duty]
        for _ in range(ticks_per_step):
            if row >= 32:
                return p
            if row == total_rows - 1:
                jump = 1 if loop else row     # loop back to row 1, or halt
            else:
                jump = 0
            _place(p, row, effect_code=0x9, effect_params=params, jump_to=jump)
            row += 1
    return p


def envelope_steps(levels: list[int], *, ticks_per_step: int = 1) -> Pattern:
    """Manual volume envelope via `Cxx` steps.

    WARNING: `Cxx` **retriggers the active note** on each application — you
    will hear a click / attack burst on every level change. This is a
    fallback for when instrument-envelope shaping isn't enough. For smooth
    release without clicks, prefer baking the envelope into the instrument
    (`initial_volume` + `vol_sweep_amount`) or use `Axy` in a subpattern.

    Included here because the corpus does use it (22 subpattern uses of
    `Cxy`, notably in FADE snare and Tempest wave instruments), so we need
    the constructor. Just be aware of the retriggering behavior.

    Halts on the final level (jump-to-self) so the envelope doesn't restart.
    """
    if not levels:
        raise ValueError("envelope_steps requires at least one level")
    p = _blank_pattern()
    total_rows = min(32, len(levels) * ticks_per_step)
    row = 0
    for level in levels:
        if not (0 <= level <= 0xF):
            raise ValueError(f"level must be 0..15, got {level}")
        for _ in range(ticks_per_step):
            if row >= 32:
                return p
            jump = row if row == total_rows - 1 else 0
            _place(p, row, effect_code=0xC, effect_params=level, jump_to=jump)
            row += 1
    return p
