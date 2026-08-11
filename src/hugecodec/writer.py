"""Version-dispatched writer for .uge files.

Serializes a `Song` dataclass back to hUGETracker's on-disk V6 or V7 format.
Structured to mirror `reader.py` — every `_write_vN` function has a
corresponding `_read_vN` you can put side-by-side to audit changes.

## Version choice

`write_song(song, target_version=None)` picks the on-disk version from:

1. Explicit `target_version` argument, if given.
2. `song.source_version`, if that is 6 or 7.
3. V7 (matches the current tracker's `WriteSongToStream`, which always
   writes V7 as of the branch this was reversed against).

V1–V5 write support is intentionally not implemented — hugecodec's authoring
workflow targets modern hUGETracker, and the tracker's own upgrade chain
handles reading old-format files.

## Correctness invariants (see NOTES.md § "OrderMatrix trailer"
## and § "Pattern insertion order")

- Patterns are serialized in `song.patterns` **dict-insertion order**, which
  the reader preserves from disk. Sorting by key here would break byte
  round-trip and disturb any tracker-side code that indexes by disk
  position.
- The order matrix is written raw: whatever length is in `order_matrix[ch]`
  is what goes on disk, trailer included. Callers should use
  `song.set_playable_orders(ch, orders)` (which appends a trailer) rather
  than writing `song.order_matrix[ch]` directly.

## Round-trip guarantee

For a `Song` parsed by `read_song`, `read_song(write_song(s)) == s` on all
fields hugecodec models. Byte-for-byte round-trip against a corpus file is
byte-identical **except** for `ShortString` padding: Pascal leaves the bytes
past `length` undefined (stack garbage); we emit zeros. This is captured in
the `test_writer_roundtrip.py` suite.
"""

from __future__ import annotations

import struct
from io import BytesIO

from .format import Instrument, Pattern, Song


class WriteError(Exception):
    """Raised when a `Song` can't be serialized cleanly."""


_SUPPORTED_VERSIONS = {6, 7}


# --------------------------------------------------------------------------- #
# Public entry                                                                #
# --------------------------------------------------------------------------- #

def write_song(song: Song, *, target_version: int | None = None) -> bytes:
    """Serialize a `Song` to `.uge` bytes.

    See module docstring for version selection semantics.
    """
    version = _pick_version(song, target_version)
    if version == 6:
        return _write_v6(song)
    if version == 7:
        return _write_v7(song)
    raise WriteError(f"unsupported target version: {version}")


def _pick_version(song: Song, target_version: int | None) -> int:
    if target_version is not None:
        if target_version not in _SUPPORTED_VERSIONS:
            raise WriteError(
                f"target_version must be one of {sorted(_SUPPORTED_VERSIONS)}, "
                f"got {target_version}"
            )
        return target_version
    if song.source_version in _SUPPORTED_VERSIONS:
        return song.source_version
    return 7


# --------------------------------------------------------------------------- #
# Primitive writers (symmetric with `_stream.ByteReader`)                     #
# --------------------------------------------------------------------------- #

def _w_int32(buf: BytesIO, v: int) -> None:
    buf.write(struct.pack("<i", v))


def _w_byte(buf: BytesIO, v: int) -> None:
    if not (0 <= v <= 255):
        raise WriteError(f"byte value out of range: {v}")
    buf.write(bytes([v]))


def _w_bool(buf: BytesIO, v: bool) -> None:
    buf.write(b"\x01" if v else b"\x00")


def _w_enum(buf: BytesIO, v: int) -> None:
    """FreePascal `$MINENUMSIZE 4` default: enums in `packed record` are 32-bit."""
    _w_int32(buf, v)


def _w_short_string(buf: BytesIO, s: str) -> None:
    """Pascal `ShortString[255]` = 1 length byte + 255 data bytes fixed (256 total).

    Bytes past `length` are undefined in real hUGETracker writes (stack
    garbage); we emit zeros. The reader ignores them, so this is semantically
    identical but not byte-identical.
    """
    encoded = s.encode("latin-1", errors="replace")
    if len(encoded) > 255:
        raise WriteError(f"ShortString too long ({len(encoded)} bytes, max 255)")
    payload = bytes([len(encoded)]) + encoded
    buf.write(payload)
    buf.write(bytes(256 - len(payload)))


def _w_ansi_string(buf: BytesIO, s: str) -> None:
    """FreePascal `TStream.WriteAnsiString` = 4-byte length prefix + N bytes.

    Empty strings write length 0 (Pascal `-1` sentinel meaning `nil` is only
    produced when the source string variable is genuinely nil, which our
    `Song.routines` never is — we always hold `""`).
    """
    encoded = s.encode("latin-1", errors="replace")
    _w_int32(buf, len(encoded))
    buf.write(encoded)


# --------------------------------------------------------------------------- #
# Compound writers                                                            #
# --------------------------------------------------------------------------- #

def _w_pattern_v2(buf: BytesIO, pattern: Pattern) -> None:
    """`TPatternV2` = 64 × `TCellV2` = 1088 bytes."""
    if len(pattern.cells) != 64:
        raise WriteError(f"pattern must have 64 rows, got {len(pattern.cells)}")
    for cell in pattern.cells:
        buf.write(struct.pack(
            "<iiii",
            cell.note,
            cell.instrument,
            cell.volume,
            cell.effect_code,
        ))
        _w_byte(buf, cell.effect_params)


def _w_instrument_v3(buf: BytesIO, inst: Instrument) -> None:
    """`TInstrumentV3` = 1385 bytes (V6+).

    Field order matches `hugedatatypes.pas:140` (TInstrumentV3 record).
    """
    start = buf.tell()
    _w_enum(buf, inst.type)                    # Type_: TInstrumentType (4)
    _w_short_string(buf, inst.name)            # Name: ShortString (256)
    _w_int32(buf, inst.length)                 # Length: Integer (4)
    _w_bool(buf, inst.length_enabled)          # LengthEnabled: Boolean (1)
    _w_byte(buf, inst.initial_volume)          # InitialVolume: 0..15 (1)
    _w_enum(buf, inst.vol_sweep_direction)     # VolSweepDirection: TSweepType (4)
    _w_byte(buf, inst.vol_sweep_amount)        # VolSweepAmount: 0..7 (1)
    _w_int32(buf, inst.sweep_time)             # SweepTime: Integer (4)
    _w_enum(buf, inst.sweep_inc_dec)           # SweepIncDec: TSweepType (4)
    _w_int32(buf, inst.sweep_shift)            # SweepShift: Integer (4)
    _w_byte(buf, inst.duty)                    # Duty: 0..3 (1)
    _w_int32(buf, inst.output_level)           # OutputLevel: Integer (4)
    _w_int32(buf, inst.waveform)               # Waveform: Integer (4)
    _w_enum(buf, inst.counter_step)            # CounterStep: TStepWidth (4)
    _w_bool(buf, inst.subpattern_enabled)      # SubpatternEnabled: Boolean (1)
    subpat = inst.subpattern if inst.subpattern is not None else Pattern()
    _w_pattern_v2(buf, subpat)                 # Subpattern: TPattern (1088)
    consumed = buf.tell() - start
    if consumed != 1385:
        raise WriteError(f"TInstrumentV3 wrote {consumed} bytes, expected 1385")


def _w_wave_bank_v2(buf: BytesIO, waves: list[bytes]) -> None:
    """16 × `TWaveV2` = 16 × 32 = 512 bytes."""
    if len(waves) != 16:
        raise WriteError(f"wave bank must have 16 slots, got {len(waves)}")
    for i, w in enumerate(waves):
        if len(w) != 32:
            raise WriteError(f"wave {i} is {len(w)} bytes (expected 32)")
        buf.write(w)


def _w_order_matrix(buf: BytesIO, matrix: list[list[int]]) -> None:
    """4 channels × `(Length: Int32, Length × Int32 pattern-keys)`.

    Writes RAW length — trailer included. Callers should use
    `song.set_playable_orders(ch, orders)` (which appends the trailer) rather
    than assigning to `song.order_matrix[ch]` directly.
    """
    if len(matrix) != 4:
        raise WriteError(f"order matrix must have 4 channels, got {len(matrix)}")
    for ch_orders in matrix:
        _w_int32(buf, len(ch_orders))
        for key in ch_orders:
            _w_int32(buf, key)


def _w_routines(buf: BytesIO, routines: list[str]) -> None:
    """Exactly 16 `AnsiString`s."""
    if len(routines) != 16:
        raise WriteError(f"routines must have 16 slots, got {len(routines)}")
    for r in routines:
        _w_ansi_string(buf, r)


def _w_instrument_collection_v3(buf: BytesIO, song: Song) -> None:
    """45 × TInstrumentV3 = 62325 bytes, laid out Duty[15], Wave[15], Noise[15].

    Slot 0 is unused in each bank (Pascal 1..15 indexing).
    """
    for bank_name, bank in (
        ("duty",  song.duty_instruments),
        ("wave",  song.wave_instruments),
        ("noise", song.noise_instruments),
    ):
        if len(bank) != 16:
            raise WriteError(
                f"{bank_name}_instruments has {len(bank)} slots (expected 16)"
            )
        for inst in bank[1:]:
            _w_instrument_v3(buf, inst)


def _w_patterns(buf: BytesIO, song: Song) -> None:
    """V5+ pattern section: Count, then (key, data) pairs in insertion order.

    Iterating `song.patterns.keys()` preserves the reader's on-disk order
    (Python 3.7+ dict is insertion-ordered). This matches the tracker's own
    `TFPGMap` iteration in `song.pas:455-459`.
    """
    _w_int32(buf, len(song.patterns))
    for key in song.patterns.keys():
        _w_int32(buf, key)
        _w_pattern_v2(buf, song.patterns[key])


# --------------------------------------------------------------------------- #
# V6 song writer                                                              #
# --------------------------------------------------------------------------- #

def _write_v6(song: Song) -> bytes:
    """Serialize as `TSongV6`. Layout mirrors `ReadSongFromStreamV6` in
    `song.pas:355-396`.
    """
    buf = BytesIO()
    _w_int32(buf, 6)
    _w_short_string(buf, song.name)
    _w_short_string(buf, song.artist)
    _w_short_string(buf, song.comment)
    _w_instrument_collection_v3(buf, song)
    _w_wave_bank_v2(buf, song.waves)

    # V6: TicksPerRow is a single Integer applied to all channels.
    tpr_set = set(song.ticks_per_row)
    if len(tpr_set) != 1:
        raise WriteError(
            f"V6 requires uniform ticks_per_row across channels, got "
            f"{song.ticks_per_row}. Use target_version=7 for per-channel speed."
        )
    _w_int32(buf, song.ticks_per_row[0])

    _w_bool(buf, song.timer_enabled)
    _w_int32(buf, song.timer_divider)

    _w_patterns(buf, song)
    _w_order_matrix(buf, song.order_matrix)
    _w_routines(buf, song.routines)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# V7 song writer                                                              #
# --------------------------------------------------------------------------- #

def _write_v7(song: Song) -> bytes:
    """Serialize as `TSongV7`. Layout mirrors `ReadSongFromStreamV7` in
    `song.pas:398-439`. Diff from V6: `TicksPerRow` is `packed array[0..3]
    of Integer` (per-channel speed).
    """
    buf = BytesIO()
    _w_int32(buf, 7)
    _w_short_string(buf, song.name)
    _w_short_string(buf, song.artist)
    _w_short_string(buf, song.comment)
    _w_instrument_collection_v3(buf, song)
    _w_wave_bank_v2(buf, song.waves)

    # V7: 4 int32s, one per channel. If the parsed song had a uniform tpr
    # (e.g., came from a V6 file), replicate; otherwise write as-is.
    if len(song.ticks_per_row) != 4:
        raise WriteError(
            f"ticks_per_row must have 4 entries for V7, got {len(song.ticks_per_row)}"
        )
    for tpr in song.ticks_per_row:
        _w_int32(buf, tpr)

    _w_bool(buf, song.timer_enabled)
    _w_int32(buf, song.timer_divider)

    _w_patterns(buf, song)
    _w_order_matrix(buf, song.order_matrix)
    _w_routines(buf, song.routines)
    return buf.getvalue()
