"""Version-dispatched reader for .uge files.

Each version's on-disk layout is described in NOTES.md. Below, each
`_read_vN` reads a single-version song into the canonical `Song` dataclass,
filling in defaults for fields introduced in later versions.

The public entry point is `read_song(path_or_bytes)`.
"""

from __future__ import annotations

import struct
from pathlib import Path

from ._stream import ByteReader
from .format import Cell, Instrument, Pattern, Song

# On-disk cell sizes
_CELL_V1_SIZE = 13
_CELL_V2_SIZE = 17

# On-disk instrument sizes
_INSTR_V1_SIZE = 304
_INSTR_V2_SIZE = 310
_INSTR_V3_SIZE = 1385

# On-disk wave sizes
_WAVE_V1_SIZE = 33
_WAVE_V2_SIZE = 32


class ReadError(Exception):
    """Raised when a .uge file can't be parsed cleanly."""


# --------------------------------------------------------------------------- #
# Public entry                                                                #
# --------------------------------------------------------------------------- #

def read_song(source: str | Path | bytes) -> Song:
    """Parse a .uge file. `source` may be a path or raw bytes."""
    if isinstance(source, (str, Path)):
        data = Path(source).read_bytes()
    else:
        data = bytes(source)

    if len(data) < 4:
        raise ReadError(f"file too small ({len(data)} bytes) to hold a version header")

    version = struct.unpack_from("<i", data, 0)[0]
    r = ByteReader(data)

    if version == 1:
        return _read_v1(r)
    if version == 2:
        return _read_v2(r)
    if version == 3:
        return _read_v3(r)
    if version == 4:
        return _read_v4(r)
    if version == 5:
        return _read_v5(r)
    if version == 6:
        return _read_v6(r)
    if version == 7:
        return _read_v7(r)
    raise ReadError(f"unsupported .uge version: {version}")


# --------------------------------------------------------------------------- #
# Instrument readers                                                          #
# --------------------------------------------------------------------------- #

def _read_instrument_v1(r: ByteReader) -> Instrument:
    """TInstrumentV1 layout — 304 bytes (V1–V3)."""
    start = r.pos
    inst = Instrument()
    inst.type = r.read_enum()
    inst.name = r.read_short_string()
    inst.length = r.read_int32()
    inst.length_enabled = r.read_bool()
    inst.initial_volume = r.read_byte()
    inst.vol_sweep_direction = r.read_enum()
    inst.vol_sweep_amount = r.read_byte()
    inst.sweep_time = r.read_int32()
    inst.sweep_inc_dec = r.read_enum()
    inst.sweep_shift = r.read_int32()
    inst.duty = r.read_byte()
    inst.output_level = r.read_int32()
    inst.waveform = r.read_int32()
    inst.shift_clock_freq = r.read_int32()
    inst.counter_step = r.read_enum()
    inst.dividing_ratio = r.read_int32()
    consumed = r.pos - start
    if consumed != _INSTR_V1_SIZE:
        raise ReadError(f"TInstrumentV1 read {consumed} bytes, expected {_INSTR_V1_SIZE}")
    return inst


def _read_instrument_v2(r: ByteReader) -> Instrument:
    """TInstrumentV2 layout — 310 bytes (V4–V5). V1 + 6-byte NoiseMacro."""
    start = r.pos
    inst = _read_instrument_v1(r)
    # NoiseMacro: array[0..5] of -31..32 (signed byte)
    inst.noise_macro = struct.unpack("<6b", r.read(6))
    consumed = r.pos - start
    if consumed != _INSTR_V2_SIZE:
        raise ReadError(f"TInstrumentV2 read {consumed} bytes, expected {_INSTR_V2_SIZE}")
    return inst


def _read_instrument_v3(r: ByteReader) -> Instrument:
    """TInstrumentV3 layout — 1385 bytes (V6+).

    Diffs from V1/V2:
      - drops ShiftClockFreq and DividingRatio
      - drops NoiseMacro (superseded by Subpattern)
      - adds SubpatternEnabled: Boolean
      - adds Subpattern: TPatternV2 (64 * 17 = 1088 bytes)
    """
    start = r.pos
    inst = Instrument()
    inst.type = r.read_enum()
    inst.name = r.read_short_string()
    inst.length = r.read_int32()
    inst.length_enabled = r.read_bool()
    inst.initial_volume = r.read_byte()
    inst.vol_sweep_direction = r.read_enum()
    inst.vol_sweep_amount = r.read_byte()
    inst.sweep_time = r.read_int32()
    inst.sweep_inc_dec = r.read_enum()
    inst.sweep_shift = r.read_int32()
    inst.duty = r.read_byte()
    inst.output_level = r.read_int32()
    inst.waveform = r.read_int32()
    inst.counter_step = r.read_enum()
    inst.subpattern_enabled = r.read_bool()
    inst.subpattern = _read_pattern_v2(r)
    consumed = r.pos - start
    if consumed != _INSTR_V3_SIZE:
        raise ReadError(f"TInstrumentV3 read {consumed} bytes, expected {_INSTR_V3_SIZE}")
    return inst


# --------------------------------------------------------------------------- #
# Cell / Pattern readers                                                      #
# --------------------------------------------------------------------------- #

def _read_pattern_v1(r: ByteReader) -> Pattern:
    """64 * TCellV1 = 832 bytes."""
    cells = []
    for _ in range(64):
        note, instrument, effect_code = struct.unpack("<iii", r.read(12))
        params = r.read_byte()
        cells.append(Cell(
            note=note,
            instrument=instrument,
            volume=0,
            effect_code=effect_code,
            effect_params=params,
        ))
    return Pattern(cells=cells)


def _read_pattern_v2(r: ByteReader) -> Pattern:
    """64 * TCellV2 = 1088 bytes."""
    cells = []
    for _ in range(64):
        note, instrument, volume, effect_code = struct.unpack("<iiii", r.read(16))
        params = r.read_byte()
        cells.append(Cell(
            note=note,
            instrument=instrument,
            volume=volume,
            effect_code=effect_code,
            effect_params=params,
        ))
    return Pattern(cells=cells)


# --------------------------------------------------------------------------- #
# Header + auxiliary readers                                                  #
# --------------------------------------------------------------------------- #

def _read_wave_bank_v1(r: ByteReader) -> tuple[list[bytes], list[int]]:
    """V1/V2: 16 * 33 bytes. We keep the first 32 as the wave and the
    vestigial 33rd byte in a separate list for round-trip fidelity."""
    waves = []
    trailer = []
    for _ in range(16):
        raw = r.read(_WAVE_V1_SIZE)
        waves.append(bytes(raw[:32]))
        trailer.append(raw[32])
    return waves, trailer


def _read_wave_bank_v2(r: ByteReader) -> list[bytes]:
    """V3+: 16 * 32 bytes."""
    return [bytes(r.read(_WAVE_V2_SIZE)) for _ in range(16)]


def _read_order_matrix(r: ByteReader) -> list[list[int]]:
    """OrderMatrix: 4 * (Length: Int32, then Length Int32s)."""
    matrix = []
    for _ in range(4):
        n = r.read_int32()
        if n < 0 or n > 1_000_000:
            raise ReadError(f"implausible order-matrix length: {n}")
        arr = list(struct.unpack(f"<{n}i", r.read(4 * n))) if n else []
        matrix.append(arr)
    return matrix


def _read_routines(r: ByteReader) -> list[str]:
    """16 AnsiStrings."""
    return [r.read_ansi_string() for _ in range(16)]


def _distribute_flat_instruments(flat: list[Instrument]) -> tuple[list[Instrument], list[Instrument], list[Instrument]]:
    """V1/V2 have a single 15-slot flat bank; V3+ split into 3 banks of 15.

    For V1/V2 files, we distribute the flat bank into 3 typed banks based on
    each instrument's `Type_` field. Slots that no instrument claims keep
    defaults. Slot 0 is unused in all banks (Pascal 1..15 indexing).
    """
    duty = [Instrument() for _ in range(16)]
    wave = [Instrument() for _ in range(16)]
    noise = [Instrument() for _ in range(16)]
    for slot_idx, inst in enumerate(flat, start=1):
        target = {0: duty, 1: wave, 2: noise}.get(inst.type)
        if target is not None:
            target[slot_idx] = inst
    return duty, wave, noise


def _read_instrument_collection_v1(r: ByteReader) -> tuple[list[Instrument], list[Instrument], list[Instrument]]:
    """V3: 45 * TInstrumentV1 = 13680 bytes, laid out as Duty[15], Wave[15], Noise[15]."""
    duty = [Instrument()] + [_read_instrument_v1(r) for _ in range(15)]
    wave = [Instrument()] + [_read_instrument_v1(r) for _ in range(15)]
    noise = [Instrument()] + [_read_instrument_v1(r) for _ in range(15)]
    return duty, wave, noise


def _read_instrument_collection_v2(r: ByteReader) -> tuple[list[Instrument], list[Instrument], list[Instrument]]:
    """V4/V5: 45 * TInstrumentV2 = 13950 bytes."""
    duty = [Instrument()] + [_read_instrument_v2(r) for _ in range(15)]
    wave = [Instrument()] + [_read_instrument_v2(r) for _ in range(15)]
    noise = [Instrument()] + [_read_instrument_v2(r) for _ in range(15)]
    return duty, wave, noise


def _read_instrument_collection_v3(r: ByteReader) -> tuple[list[Instrument], list[Instrument], list[Instrument]]:
    """V6+: 45 * TInstrumentV3 = 62325 bytes."""
    duty = [Instrument()] + [_read_instrument_v3(r) for _ in range(15)]
    wave = [Instrument()] + [_read_instrument_v3(r) for _ in range(15)]
    noise = [Instrument()] + [_read_instrument_v3(r) for _ in range(15)]
    return duty, wave, noise


# --------------------------------------------------------------------------- #
# Version-specific song readers                                               #
# --------------------------------------------------------------------------- #

def _read_v1(r: ByteReader) -> Song:
    song = Song(source_version=1)
    version = r.read_int32()
    assert version == 1
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    flat = [_read_instrument_v1(r) for _ in range(15)]
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _distribute_flat_instruments(flat)
    waves, trailer = _read_wave_bank_v1(r)
    song.waves = waves
    song._v1_wave_trailer = trailer
    tpr = r.read_int32()
    song.ticks_per_row = [tpr, tpr, tpr, tpr]

    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for i in range(count):
        song.patterns[i] = _read_pattern_v1(r)
    song.order_matrix = _read_order_matrix(r)
    # V1 has no routines
    return song


def _read_v2(r: ByteReader) -> Song:
    song = _read_v1(r)
    song.source_version = 2
    # Position was left at the end of order_matrix; routines follow
    # But we've already returned from _read_v1 which used the same reader.
    # We need to read routines here — the reader position carried through.
    song.routines = _read_routines(r)
    return song


def _read_v3(r: ByteReader) -> Song:
    song = Song(source_version=3)
    version = r.read_int32()
    assert version == 3
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _read_instrument_collection_v1(r)
    song.waves = _read_wave_bank_v2(r)
    tpr = r.read_int32()
    song.ticks_per_row = [tpr, tpr, tpr, tpr]

    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for i in range(count):
        song.patterns[i] = _read_pattern_v1(r)
    song.order_matrix = _read_order_matrix(r)
    song.routines = _read_routines(r)
    return song


def _read_v4(r: ByteReader) -> Song:
    song = Song(source_version=4)
    version = r.read_int32()
    assert version == 4
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _read_instrument_collection_v2(r)
    song.waves = _read_wave_bank_v2(r)
    tpr = r.read_int32()
    song.ticks_per_row = [tpr, tpr, tpr, tpr]

    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for i in range(count):
        song.patterns[i] = _read_pattern_v1(r)
    song.order_matrix = _read_order_matrix(r)
    song.routines = _read_routines(r)
    return song


def _read_v5(r: ByteReader) -> Song:
    song = Song(source_version=5)
    version = r.read_int32()
    assert version == 5
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _read_instrument_collection_v2(r)
    song.waves = _read_wave_bank_v2(r)
    tpr = r.read_int32()
    song.ticks_per_row = [tpr, tpr, tpr, tpr]

    # V5+: patterns stored with explicit keys
    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for _ in range(count):
        key = r.read_int32()
        song.patterns[key] = _read_pattern_v1(r)
    song.order_matrix = _read_order_matrix(r)
    song.routines = _read_routines(r)
    return song


def _read_v6(r: ByteReader) -> Song:
    song = Song(source_version=6)
    version = r.read_int32()
    assert version == 6
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _read_instrument_collection_v3(r)
    song.waves = _read_wave_bank_v2(r)
    tpr = r.read_int32()
    song.ticks_per_row = [tpr, tpr, tpr, tpr]
    song.timer_enabled = r.read_bool()
    song.timer_divider = r.read_int32()

    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for _ in range(count):
        key = r.read_int32()
        song.patterns[key] = _read_pattern_v2(r)
    song.order_matrix = _read_order_matrix(r)
    song.routines = _read_routines(r)
    return song


def _read_v7(r: ByteReader) -> Song:
    song = Song(source_version=7)
    version = r.read_int32()
    assert version == 7
    song.name = r.read_short_string()
    song.artist = r.read_short_string()
    song.comment = r.read_short_string()
    song.duty_instruments, song.wave_instruments, song.noise_instruments = \
        _read_instrument_collection_v3(r)
    song.waves = _read_wave_bank_v2(r)
    # V7: per-channel TicksPerRow (4 ints)
    song.ticks_per_row = list(struct.unpack("<4i", r.read(16)))
    song.timer_enabled = r.read_bool()
    song.timer_divider = r.read_int32()

    count = r.read_int32()
    if count < 0 or count > 100_000:
        raise ReadError(f"implausible pattern count: {count}")
    for _ in range(count):
        key = r.read_int32()
        song.patterns[key] = _read_pattern_v2(r)
    song.order_matrix = _read_order_matrix(r)
    song.routines = _read_routines(r)
    return song
