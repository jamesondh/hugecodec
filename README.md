# hugecodec

A parser (and eventually writer) for hUGETracker `.uge` files, aimed at making
songs analyzable, diffable, and LLM-editable.

hUGETracker (https://github.com/SuperDisk/hUGETracker) is a music tracker for
the original Game Boy. Its native `.uge` format is a Pascal-serialized binary
blob — great for the tracker, opaque to anything else. `hugecodec` decodes it
to an in-memory dataclass tree that you can dump as JSON today and, later,
round-trip through a text DSL suitable for working with an LLM.

## Status

Reader supports V1–V7. Writer supports V6 and V7 (byte-perfect round-trip
modulo Pascal `ShortString` stack padding — verified against every V6
corpus file). Upgrade chain and text DSL are planned.

## Install

```bash
# Nothing to install — stdlib only.
git clone <this repo> && cd hugecodec
python3 -m src.hugecodec dump song.uge
```

## Usage

```bash
python3 -m src.hugecodec dump  path/to/song.uge          # pretty JSON to stdout
python3 -m src.hugecodec dump  path/to/song.uge --compact
python3 -m src.hugecodec info  path/to/song.uge          # header-only summary
python3 -m src.hugecodec waves path/to/song.uge          # wave-bank spectral report
python3 -m src.hugecodec waves path/to/song.uge --wave 3 # analyze one wave
python3 -m src.hugecodec waves path/to/song.uge --all --no-shape
```

The `waves` subcommand runs a DFT on each wave in the song's 16-slot bank,
identifies dominant partials, and classifies the wave (interval dyad,
triad, pulse, single-partial, harmonic mix). Names of any wave instruments
pointing at the slot are cross-referenced in the header.

## Programmatic wave synthesis

```python
from hugecodec import interval_wave, from_harmonics

# FADE-style close-bin dyads. Only these four intervals reliably read as
# two audible pitches on the wave channel; wider ratios collapse into a
# single colored timbre and are rejected.
w = interval_wave("m3")             # bins 5:6 → 32 nibbles
w = interval_wave("M3")             # bins 4:5
w = interval_wave("P4")             # bins 3:4
w = interval_wave("P5")             # bins 2:3

# Custom additive design — honest low-level API. No claims about how the
# resulting wave will be perceived; useful for timbral experiments.
w = from_harmonics([(3, 1.0), (5, 0.5), (7, 0.25)])

print(w.to_hex())                   # → paste into hUGETracker's wave editor
```

There is deliberately no `triad_wave()` or `seventh_wave()`. A single
32-sample periodic waveform is one pitched source, not multiple voices —
"minor triad at bins 10:12:15" isn't a chord, it's upper harmonics of the
tracker note. See `NOTES.md` "Wave-channel sample interpretation" for the
perceptual analysis and the space of interesting timbres this opens up.

## Serum 2 wavetable export

For auditioning wave-channel timbres in a modern DAW (compose in FL,
audition through Serum), the `wavetable` subcommand emits Serum-2-shaped
WAV files — 2048-sample single-cycle frames with a RIFF `clm ` chunk so
Serum treats the file as a pre-formatted wavetable instead of running
frequency-estimation on it.

```bash
python3 -m hugecodec wavetable packs                                # list curated packs
python3 -m hugecodec wavetable single formant-mid --out formant-mid.wav
python3 -m hugecodec wavetable pack --preset seventh-chords --out sevenths.wav
python3 -m hugecodec wavetable pack --frames p8,thickener,formant-mid --out mix.wav
python3 -m hugecodec wavetable all --out ./serum-tables/           # everything
```

Each 32-sample GB wave is zero-order-hold-expanded to 2048 samples (each
nibble repeated 64×) so the DAC stair-step character is preserved
exactly — no FFT smoothing, no invented harmonics. Serum's own mipmap
playback handles anti-aliasing. Multi-frame packs concatenate related
presets so Serum's WT-position knob morphs through them.

Single-frame WAVs are ~4 KB (vs ~176 KB for the `audition render` tone
outputs), and they load directly as wavetables rather than triggering
sample-import analysis.

## Tests

```bash
python3 tests/test_roundtrip.py     # parse every sample without crashing
python3 tests/test_writer.py        # writer semantic + byte-diff round-trip
python3 tests/test_waves.py         # spectral analysis + synthesis checks
python3 tests/test_wavetable.py     # Serum-shaped WAV emitter checks
```

Test corpus lives at `~/hugetracker-sample-songs/` — 22 files spanning V1–V6.

## Writing songs

```python
from hugecodec import read_song, write_song
from hugecodec.subpatterns import arp_cycle, kick_transient, duty_morph

song = read_song("song.uge")

# Modify — e.g. attach a broken-chord arp to the wave instrument.
song.wave_instruments[1].subpattern_enabled = True
song.wave_instruments[1].subpattern = arp_cycle([0, 3, 7], ticks_per_step=4)

# When editing the order matrix, use the trailer-aware helpers:
song.set_playable_orders(0, [0, 1, 2])   # writes [0, 1, 2, 0] on disk

Path("song-mod.uge").write_bytes(write_song(song))
```

The writer defaults to `song.source_version` (V6 or V7); pass
`target_version=7` to explicitly upgrade a V6 song.

`hugecodec.subpatterns` provides constructors for the common corpus
shapes — `pluck`, `kick_transient`, `hat_flat`, `arp_cycle`,
`vibrato_ramp`, `duty_morph`, `envelope_steps`. Each handles the
compiled-32-row limit and the `Volume`-field-as-jump-target loop
semantics.

## Effect reference

`EFFECTS.md` documents every effect with (a) the docs summary, (b)
corpus usage counts / typical params, (c) hugecodec misuse examples
and how to avoid them. The row-scoped-only rule is the most important
thing there — effects apply only on the row they appear on unless
re-entered on every affected row (or placed in a subpattern).

## Analysis scripts

```bash
python3 tests/analyze_effects.py            # per-effect usage across corpus
python3 tests/analyze_subpatterns.py        # subpattern shape catalog
```

## Format notes

See `NOTES.md` for reverse-engineering notes, on-disk layout tables, and open
questions.

## License

MIT (see LICENSE, TBD).
