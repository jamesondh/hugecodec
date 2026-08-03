"""Command-line entry point.

Usage:
    hugecodec dump song.uge [--compact] [--include-defaults]
    hugecodec info song.uge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .format import INSTR_TYPE_NAMES
from .json_dump import song_to_json
from .reader import read_song, ReadError


def _cmd_dump(args: argparse.Namespace) -> int:
    try:
        song = read_song(args.path)
    except ReadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(song_to_json(
        song,
        indent=None if args.compact else 2,
        include_defaults=args.include_defaults,
    ))
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    try:
        song = read_song(args.path)
    except ReadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"file:            {args.path}")
    print(f"source version:  V{song.source_version}")
    print(f"name:            {song.name!r}")
    print(f"artist:          {song.artist!r}")
    print(f"comment:         {song.comment!r}")
    if len(set(song.ticks_per_row)) == 1:
        print(f"ticks/row:       {song.ticks_per_row[0]} (all channels)")
    else:
        print(f"ticks/row:       {song.ticks_per_row}")
    print(f"timer:           enabled={song.timer_enabled} divider={song.timer_divider}")

    total = len(song.patterns)
    print(f"patterns:        {total} unique (keys {min(song.patterns) if song.patterns else 0}..{max(song.patterns) if song.patterns else 0})")

    for i, ch in enumerate(["CH1", "CH2", "CH3", "CH4"]):
        n = len(song.order_matrix[i])
        keys = song.order_matrix[i]
        preview = ", ".join(str(k) for k in keys[:12])
        if len(keys) > 12:
            preview += ", …"
        print(f"  {ch} orders:   {n:3d}  [{preview}]")

    print()
    print("Non-default instruments:")
    for label, bank in [("Duty", song.duty_instruments),
                        ("Wave", song.wave_instruments),
                        ("Noise", song.noise_instruments)]:
        for slot, inst in enumerate(bank[1:], start=1):
            if inst.name or inst.initial_volume != 0:
                type_name = INSTR_TYPE_NAMES.get(inst.type, "?")
                print(f"  {label:5s} {slot:2d}  [{type_name:6s}]  {inst.name!r}")

    routines = [(i, r) for i, r in enumerate(song.routines) if r]
    if routines:
        print()
        print("Non-empty routines:")
        for i, r in routines:
            print(f"  routine {i}: {r!r}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hugecodec", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dump", help="dump a .uge as JSON")
    d.add_argument("path", type=Path)
    d.add_argument("--compact", action="store_true", help="single-line JSON")
    d.add_argument("--include-defaults", action="store_true",
                   help="include default-valued fields (verbose)")
    d.set_defaults(func=_cmd_dump)

    i = sub.add_parser("info", help="header-only human-readable summary")
    i.add_argument("path", type=Path)
    i.set_defaults(func=_cmd_info)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
