"""Catalog subpattern shapes across the V6+ corpus.

Every enabled subpattern in the corpus is a short vertical grid — up to 64
rows, one row per tick — describing a per-tick modulation of the base note.
This script categorizes recurring shapes so `src/hugecodec/subpatterns.py`
can generalize them.

Categories reported:
  - "size": how many non-empty rows in the subpattern
  - "kind" heuristic:
      * "kick"       → CH4/noise, negative pitch offsets in first few rows
      * "arp"        → cycling offset column, no other effects
      * "pluck"      → positive offset row 0, back to 0 immediately
      * "vibrato"    → 4xy effects on many rows
      * "envelope"   → Cxx/Axx effects (volume shaping)
      * "duty-morph" → 9xx effects across rows
      * "mixed"      → uses multiple mechanisms
      * "other"      → doesn't match a heuristic
  - jump semantics: does it self-loop, jump-to-self (halt), or run once?
"""

from __future__ import annotations

import argparse
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hugecodec import read_song  # noqa: E402
from hugecodec.format import NOTE_EMPTY  # noqa: E402


DEFAULT_CORPUS = Path.home() / "hugetracker-sample-songs"


def summarize_subpattern(pat, bank: str, slot: int, inst_name: str) -> dict:
    """Return a summary dict for one subpattern."""
    used_rows = []
    for i, cell in enumerate(pat.cells):
        if cell.has_note or cell.has_effect or cell.volume != 0:
            used_rows.append(i)
    size = max(used_rows) + 1 if used_rows else 0

    # Effect distribution
    effect_codes = Counter()
    for cell in pat.cells[:size]:
        if cell.has_effect:
            effect_codes[cell.effect_code] += 1

    # Offset semantics: in a subpattern, the `note` field is a semitone offset
    # (0..N; negative offsets not directly supported per the docs — "offset is
    # a positive number of semitones added to the base note").
    offsets = [cell.note for cell in pat.cells[:size] if cell.note != NOTE_EMPTY]

    # Jump column: hUGETracker's subpattern grid displays a `jump` column, but
    # in the on-disk TCellV2 there's no dedicated jump field. Looking at
    # `subpatterns.md`, the jump column is inferred from... unclear from the
    # docs; would need to inspect the tracker's subpattern editor code.
    # For this audit we skip jump semantics and focus on offset+effect shape.

    # Kind heuristic
    kind = classify_shape(bank, offsets, effect_codes)

    return {
        "bank": bank,
        "slot": slot,
        "inst_name": inst_name,
        "size": size,
        "effect_codes": dict(effect_codes),
        "offsets": offsets,
        "kind": kind,
    }


def classify_shape(bank: str, offsets: list[int], effects: Counter) -> str:
    if bank == "noise":
        # Percussion instruments — offsets often shift pitch for the transient
        if offsets and any(o > 20 for o in offsets[:3]):
            return "kick/tom (high-pitch transient)"
        if offsets and offsets[0] > 0:
            return "noise (offset envelope)"
        return "noise (flat)"
    if 0x9 in effects and effects[0x9] >= 3:
        return "timbre-morph"
    if 0x4 in effects and effects[0x4] >= 3:
        return "vibrato"
    if 0xC in effects or 0xA in effects:
        return "envelope (Cxx/Axx)"
    if len(offsets) >= 3 and offsets != sorted(offsets):
        return "arp"
    if offsets and offsets[0] > 6 and (len(offsets) < 3 or offsets[1] == 0):
        return "pluck"
    if any(effects.values()):
        return "mixed"
    if offsets:
        return "offset-only"
    return "empty/enabled"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=None)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.path is not None:
        paths = [args.path]
    else:
        paths = sorted(Path(p) for p in glob.glob(str(args.corpus / "*.uge")))

    all_subs = []
    for path in paths:
        try:
            song = read_song(path)
        except Exception as e:
            print(f"  [WARN] {path.name}: {e}", file=sys.stderr)
            continue
        if song.source_version < 6:
            continue
        for bank_label, bank in (
            ("duty",  song.duty_instruments),
            ("wave",  song.wave_instruments),
            ("noise", song.noise_instruments),
        ):
            for slot, inst in enumerate(bank):
                if not inst.subpattern_enabled or inst.subpattern is None:
                    continue
                summary = summarize_subpattern(inst.subpattern, bank_label, slot, inst.name)
                summary["song"] = path.name
                all_subs.append(summary)

    if not all_subs:
        print("no enabled subpatterns found")
        return 0

    # Overall counts by kind
    kind_counts = Counter(s["kind"] for s in all_subs)
    print("Subpattern kinds (across corpus):")
    for k, c in kind_counts.most_common():
        print(f"  {c:3d}  {k}")

    # Per-bank breakdown
    print("\nBy bank:")
    for bank in ("duty", "wave", "noise"):
        bank_subs = [s for s in all_subs if s["bank"] == bank]
        print(f"  {bank:5s} {len(bank_subs):3d} enabled subpatterns")

    # Show first few examples of each kind
    print("\nExamples (first 3 of each kind):")
    by_kind = defaultdict(list)
    for s in all_subs:
        by_kind[s["kind"]].append(s)
    for kind in sorted(by_kind, key=lambda k: -len(by_kind[k])):
        print(f"\n  --- {kind} ({len(by_kind[kind])} total) ---")
        for s in by_kind[kind][:3]:
            fx = ", ".join(f"{c:X}xy×{n}" for c, n in s["effect_codes"].items()) or "no effects"
            print(f"    {s['song']:52s} {s['bank']}[{s['slot']}] '{s['inst_name']}'")
            print(f"      size={s['size']} offsets={s['offsets'][:12]}{'...' if len(s['offsets'])>12 else ''}  effects: {fx}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
