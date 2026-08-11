"""Per-effect cross-corpus audit.

For each effect code 0..F, tabulate:
  - total uses (main patterns only; subpattern uses reported separately)
  - typical param distribution (top-N by frequency)
  - per-channel breakdown (which channels each effect appears on)
  - "shape" heuristics — does this effect usually appear alone on a cell,
    or paired with a note? On empty rows? Repeated across rows?

Intended as the empirical ground-truth for `EFFECTS.md`. Run against the
whole corpus (default) or a single song.

Usage:
    python3 tests/analyze_effects.py              # whole corpus
    python3 tests/analyze_effects.py path/to.uge  # single song
    python3 tests/analyze_effects.py --effect 9   # focus on one effect
"""

from __future__ import annotations

import argparse
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hugecodec import read_song  # noqa: E402
from hugecodec.format import NOTE_EMPTY, NOTE_OFF  # noqa: E402


DEFAULT_CORPUS = Path.home() / "hugetracker-sample-songs"

EFFECT_NAMES = {
    0x0: "Arpeggio",
    0x1: "Portamento up",
    0x2: "Portamento down",
    0x3: "Tone portamento",
    0x4: "Vibrato",
    0x5: "Set master volume",
    0x6: "Call routine",
    0x7: "Note delay",
    0x8: "Set panning",
    0x9: "Change timbre",
    0xA: "Volume slide",
    0xB: "Position jump",
    0xC: "Set volume",
    0xD: "Pattern break",
    0xE: "Note cut",
    0xF: "Set tempo",
}


def gather_effect_uses(paths: list[Path]) -> dict[int, list[dict]]:
    """Return { effect_code: [use_record, ...] }.

    Each use_record is:
        { song, version, source: "main"|"sub", channel_hint, pat_key,
          row, note, instrument, params }
    """
    uses: dict[int, list[dict]] = defaultdict(list)

    for path in paths:
        try:
            song = read_song(path)
        except Exception as e:
            print(f"  [WARN] read failed {path.name}: {e}", file=sys.stderr)
            continue

        # Which channels does each pattern key belong to? Look at the order
        # matrix. A pattern can appear on multiple channels; we record all.
        pat_channels: dict[int, set[int]] = defaultdict(set)
        for ch in range(4):
            for key in song.order_matrix[ch]:
                pat_channels[key].add(ch)

        # Main patterns
        for key, pat in song.patterns.items():
            for row, cell in enumerate(pat.cells):
                if not cell.has_effect:
                    continue
                uses[cell.effect_code].append({
                    "song": path.name,
                    "version": song.source_version,
                    "source": "main",
                    "channels": sorted(pat_channels.get(key, set())),
                    "pat_key": key,
                    "row": row,
                    "note": cell.note,
                    "instrument": cell.instrument,
                    "params": cell.effect_params,
                })

        # Subpatterns (V6+ instruments) — record which bank the instrument is in
        for bank_label, bank, ch_hint in (
            ("duty",  song.duty_instruments,  [0, 1]),
            ("wave",  song.wave_instruments,  [2]),
            ("noise", song.noise_instruments, [3]),
        ):
            for slot, inst in enumerate(bank):
                if not inst.subpattern_enabled or inst.subpattern is None:
                    continue
                for row, cell in enumerate(inst.subpattern.cells):
                    if not cell.has_effect:
                        continue
                    uses[cell.effect_code].append({
                        "song": path.name,
                        "version": song.source_version,
                        "source": f"sub:{bank_label}[{slot}]",
                        "channels": ch_hint,
                        "pat_key": None,
                        "row": row,
                        "note": cell.note,
                        "instrument": cell.instrument,
                        "params": cell.effect_params,
                    })

    return uses


def summarize_effect(code: int, records: list[dict]) -> None:
    """Print a summary of usage for one effect."""
    name = EFFECT_NAMES.get(code, "?")
    print(f"\n=== 0x{code:X}  {name}  ({len(records)} uses) ===")

    if not records:
        print("  (no uses in corpus)")
        return

    main = [r for r in records if r["source"] == "main"]
    sub = [r for r in records if r["source"] != "main"]
    print(f"  main: {len(main)}   subpattern: {len(sub)}")

    # Param distribution
    param_counts = Counter(r["params"] for r in records)
    top_params = param_counts.most_common(10)
    print(f"  top params: {', '.join(f'{code:X}{p:02X}={c}' for p, c in top_params)}")

    # Channel distribution (main only — subpatterns have known channel hints)
    ch_counts: Counter = Counter()
    for r in main:
        for ch in r["channels"] or [None]:
            ch_counts[ch] += 1
    ch_str = ", ".join(f"CH{c+1 if c is not None else '?'}={n}" for c, n in sorted(ch_counts.items(), key=lambda x: (x[0] is None, x[0])))
    print(f"  main channels: {ch_str}")

    # Note-on-same-cell distribution
    with_note = sum(1 for r in records if r["note"] not in (NOTE_EMPTY, NOTE_OFF))
    without = len(records) - with_note
    print(f"  cell has note: {with_note}    empty note (effect-only cell): {without}")

    # Song distribution (top-3 songs using this effect)
    song_counts = Counter(r["song"] for r in records)
    print(f"  used in {len(song_counts)} songs; top: {', '.join(f'{s}={c}' for s, c in song_counts.most_common(3))}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=None,
                        help="single .uge file (default: whole corpus)")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--effect", type=lambda s: int(s, 16), default=None,
                        help="restrict output to one effect code (hex)")
    args = parser.parse_args()

    if args.path is not None:
        paths = [args.path]
    else:
        paths = sorted(Path(p) for p in glob.glob(str(args.corpus / "*.uge")))

    uses = gather_effect_uses(paths)

    codes = [args.effect] if args.effect is not None else list(range(0x10))
    for code in codes:
        summarize_effect(code, uses.get(code, []))

    return 0


if __name__ == "__main__":
    sys.exit(main())
