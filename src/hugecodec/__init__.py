"""hugecodec — parser and (eventually) writer for hUGETracker .uge files."""

from .format import (
    Song,
    Instrument,
    Cell,
    Pattern,
    NOTE_EMPTY,
    NOTE_OFF,
    INSTRUMENT_EMPTY,
    VOLUME_EMPTY,
    EFFECT_EMPTY,
)
from .reader import read_song, ReadError
from .waves import (
    Wave,
    WaveReport,
    analyze,
    from_harmonics,
    interval_wave,
    wave_from_song_bank,
)

__all__ = [
    "Song",
    "Instrument",
    "Cell",
    "Pattern",
    "NOTE_EMPTY",
    "NOTE_OFF",
    "INSTRUMENT_EMPTY",
    "VOLUME_EMPTY",
    "EFFECT_EMPTY",
    "read_song",
    "ReadError",
    # waves
    "Wave",
    "WaveReport",
    "analyze",
    "from_harmonics",
    "interval_wave",
    "wave_from_song_bank",
]
