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
from .waves import Wave, analyze, WAVE_MAX


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


def _wave_referrers(song, bank_index: int) -> list[tuple[int, str]]:
    """List (instrument_slot, name) pairs of Wave instruments pointing at bank_index."""
    out: list[tuple[int, str]] = []
    for slot, inst in enumerate(song.wave_instruments):
        if slot == 0:
            continue  # Pascal slot 0 unused
        if inst.waveform == bank_index and (inst.name or inst.initial_volume != 0):
            out.append((slot, inst.name))
    return out


def _print_wave_analysis(bank_index: int,
                         wave: Wave,
                         referrers: list[tuple[int, str]],
                         show_shape: bool,
                         top_bins: int) -> None:
    """Print a single wave's analysis block."""
    report = analyze(wave, top_n=top_bins)
    refs = ", ".join(f"#{slot} {name!r}" for slot, name in referrers) or "(unreferenced)"
    print(f"bank[{bank_index:2d}]  used by: {refs}")
    print(f"  hex: {wave.to_hex()}")
    print(f"  DC={report.dc_offset:.2f}  AC={report.ac_energy:.2f}  "
          f"kind={report.inferred_kind}")
    print(f"  → {report.description}")

    # Top peaks with mini-bars, scaled to the strongest non-DC bin
    if report.peaks:
        max_mag = max(p.magnitude for p in report.peaks) or 1.0
        print("  FFT peaks:")
        for p in report.peaks:
            bar_len = int(round(p.magnitude / max_mag * 24))
            print(f"    bin {p.bin:2d}: {p.magnitude:6.2f}  {'|' * bar_len}")

    if show_shape:
        print("  shape:")
        for row in wave.ascii_shape(rows=10):
            print(f"    {row}")
    print()


def _cmd_waves(args: argparse.Namespace) -> int:
    try:
        song = read_song(args.path)
    except ReadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"file: {args.path}")
    print(f"source version: V{song.source_version}")
    print()

    silent = bytes(len(song.waves[0]))  # all-zero comparison
    indices: list[int]
    if args.wave is not None:
        if not (0 <= args.wave < len(song.waves)):
            print(f"error: --wave must be 0..{len(song.waves)-1}", file=sys.stderr)
            return 1
        indices = [args.wave]
    else:
        indices = list(range(len(song.waves)))

    printed = 0
    for i in indices:
        raw = song.waves[i]
        is_silent = raw == silent
        # Skip silent+unreferenced unless --all
        referrers = _wave_referrers(song, i)
        if not args.all and is_silent and not referrers:
            continue
        wave = Wave.from_bytes(raw)
        _print_wave_analysis(
            bank_index=i,
            wave=wave,
            referrers=referrers,
            show_shape=not args.no_shape,
            top_bins=args.top_bins,
        )
        printed += 1

    if printed == 0:
        print("(no non-silent, referenced waves — try --all)")
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

    w = sub.add_parser(
        "waves",
        help="spectral analysis of wave-bank contents",
        description=(
            "Report DFT peaks, detected intervals, and an ASCII shape for each "
            "wave in the song's 16-slot wave bank. By default, silent and "
            "unreferenced slots are omitted."
        ),
    )
    w.add_argument("path", type=Path)
    w.add_argument("--wave", type=int, default=None,
                   help="analyze only bank[N] (0..15)")
    w.add_argument("--all", action="store_true",
                   help="include silent / unreferenced slots")
    w.add_argument("--no-shape", action="store_true",
                   help="omit the ASCII wave plot")
    w.add_argument("--top-bins", type=int, default=6,
                   help="how many FFT peaks to list per wave (default 6)")
    w.set_defaults(func=_cmd_waves)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
