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
    interval_wave_reinforced,
    wave_from_song_bank,
    render_wav,
    note_to_hz,
    NOTE_HZ,
)
from .presets import PRESETS, PRESET_CATEGORIES

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
    "interval_wave_reinforced",
    "wave_from_song_bank",
    "render_wav",
    "note_to_hz",
    "NOTE_HZ",
    # presets
    "PRESETS",
    "PRESET_CATEGORIES",
]
