# hugecodec

A parser (and eventually writer) for hUGETracker `.uge` files, aimed at making
songs analyzable, diffable, and LLM-editable.

hUGETracker (https://github.com/SuperDisk/hUGETracker) is a music tracker for
the original Game Boy. Its native `.uge` format is a Pascal-serialized binary
blob — great for the tracker, opaque to anything else. `hugecodec` decodes it
to an in-memory dataclass tree that you can dump as JSON today and, later,
round-trip through a text DSL suitable for co-writing with an LLM.

## Status

Reader only, versions V1–V6. V7 support pending a V7 sample file (none in the
current corpus). Writer, upgrade chain, and text DSL are all planned.

## Install

```bash
# Nothing to install — stdlib only.
git clone <this repo> && cd hugecodec
python3 -m src.hugecodec dump song.uge
```

## Usage

```bash
python3 -m src.hugecodec dump path/to/song.uge          # pretty JSON to stdout
python3 -m src.hugecodec dump path/to/song.uge --compact
python3 -m src.hugecodec info path/to/song.uge          # header-only summary
```

## Tests

```bash
python3 tests/test_roundtrip.py                 # dump every sample without crashing
python3 tests/test_roundtrip.py /path/to/song   # dump a single file (debug)
```

Test corpus lives at `~/hugetracker-sample-songs/` — 22 files spanning V1–V6.

## Format notes

See `NOTES.md` for reverse-engineering notes, on-disk layout tables, and open
questions.

## License

MIT (see LICENSE, TBD).
