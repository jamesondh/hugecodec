"""JSON dumper for `Song`. Debug/inspection tool, not the eventual text DSL."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .format import Cell, Instrument, Pattern, Song, INSTR_TYPE_NAMES


def song_to_dict(song: Song, *, include_defaults: bool = False) -> dict[str, Any]:
    """Convert a Song to a nested dict suitable for `json.dumps`.

    When `include_defaults=False` (the default), fields whose values equal
    the dataclass default are omitted from instrument/cell dicts — this makes
    pattern grids readable instead of walls of zeros.
    """
    return {
        "source_version": song.source_version,
        "name": song.name,
        "artist": song.artist,
        "comment": song.comment,
        "ticks_per_row": song.ticks_per_row,
        "timer_enabled": song.timer_enabled,
        "timer_divider": song.timer_divider,
        "duty_instruments": _instruments_to_list(song.duty_instruments, include_defaults),
        "wave_instruments": _instruments_to_list(song.wave_instruments, include_defaults),
        "noise_instruments": _instruments_to_list(song.noise_instruments, include_defaults),
        "waves": [_bytes_to_hex(w) for w in song.waves],
        "patterns": {
            str(k): _pattern_to_list(p, include_defaults)
            for k, p in sorted(song.patterns.items())
        },
        "order_matrix": {
            "ch1": song.order_matrix[0],
            "ch2": song.order_matrix[1],
            "ch3": song.order_matrix[2],
            "ch4": song.order_matrix[3],
        },
        "routines": song.routines,
    }


def song_to_json(song: Song, *, indent: int | None = 2, include_defaults: bool = False) -> str:
    return json.dumps(
        song_to_dict(song, include_defaults=include_defaults),
        indent=indent,
        ensure_ascii=False,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

_DEFAULT_INSTRUMENT = Instrument()
_DEFAULT_CELL = Cell()


def _instruments_to_list(bank: list[Instrument], include_defaults: bool) -> list[dict[str, Any] | None]:
    """Skip slot 0 (unused, Pascal 1..15). Return 15 entries."""
    return [_instrument_to_dict(inst, include_defaults) for inst in bank[1:]]


def _instrument_to_dict(inst: Instrument, include_defaults: bool) -> dict[str, Any] | None:
    """Serialize an instrument. If it's the default (empty slot) and defaults
    are being skipped, return None."""
    d = asdict(inst)
    d["type_name"] = INSTR_TYPE_NAMES.get(inst.type, f"unknown({inst.type})")
    if inst.subpattern is not None:
        d["subpattern"] = _pattern_to_list(inst.subpattern, include_defaults)
    if not include_defaults:
        if inst == _DEFAULT_INSTRUMENT:
            return None
        d = {k: v for k, v in d.items() if v != getattr(_DEFAULT_INSTRUMENT, k, object())}
        d["type_name"] = INSTR_TYPE_NAMES.get(inst.type, f"unknown({inst.type})")
    return d


def _pattern_to_list(pattern: Pattern, include_defaults: bool) -> list[dict[str, Any] | str]:
    """One entry per row. '.' for a wholly-empty row when defaults are hidden."""
    out = []
    for cell in pattern.cells:
        if not include_defaults and cell == _DEFAULT_CELL:
            out.append(".")
        else:
            out.append({
                "note": cell.note,
                "instrument": cell.instrument,
                "volume": cell.volume,
                "effect": cell.effect_str(),
            })
    return out


def _bytes_to_hex(b: bytes) -> str:
    """32-byte wave → 64-char hex string."""
    return b.hex()
