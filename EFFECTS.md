# hUGETracker effect reference (annotated for hugecodec)

Mirrors the effect table at
[superdisk.github.io/hUGETracker/hUGETracker/effect-reference.html][ref]
(source: `hUGETracker/manual/src/hUGETracker/effect-reference.md`), with
corpus usage data and a log of hugecodec mistakes to avoid repeating.

[ref]: https://superdisk.github.io/hUGETracker/hUGETracker/effect-reference.html

## Read this first

**Effects only apply on the row they appear on.** From the manual: *"if you
want an effect to remain active for several rows, you must re-enter it on
each one."* This is the single most-violated rule in the initial hugecodec
work — vibrato ramps, arpeggios, and duty morphs will silently do nothing
past their first row unless you either (a) repeat the effect cell on every
row of the sustain, or (b) put it in the instrument's subpattern (which
runs per-tick, see § "Subpatterns" below).

**"Playing note"** = the last note played on the channel thus far. An
effect on an empty-note row applies to whatever note is still active.

## Effect table

Every effect below is documented as: **code + name**, docs summary, corpus
usage counts across the 22-file sample corpus (from
`tests/analyze_effects.py`), and any hugecodec-specific gotchas.

| Effect | Name | Docs summary |
|--------|------|--------------|
| `0xy`  | Arpeggio          | Each tick, cycle base note → +x semi → +y semi → base. |
| `1xx`  | Portamento up     | Slide pitch up `xx` units/tick. Skipped on the row's first tick if the row has a note. Tempo=1 defeats it entirely. |
| `2xx`  | Portamento down   | Same but down. |
| `3xx`  | Tone portamento   | **Instead of playing the cell's note**, slide toward it at `xx` units/tick. Stops exactly at the note. |
| `4xy`  | Vibrato           | Every `x+1` ticks, switch between playing note and `note+y units`. Units, not semitones. |
| `5xx`  | Set master volume | NR50 both speakers. Volume 0 ≠ silent. |
| `6xy`  | Call routine      | Call user-defined routine `y`. Zero uses in the corpus. |
| `7xx`  | Note delay        | Wait `xx` ticks before playing the row's note. `xx > tempo` = no play. |
| `8xx`  | Set panning       | NR51. Setting both speakers off mutes (not recommended). |
| `9xx`  | Change timbre     | CH1/2 = duty cycle (`900/940/980/9C0` = 12.5/25/50/75%). CH3 = load wave slot `xx` (**restarts note**). CH4 = LFSR width (short-mode transition **can lock up the channel**). |
| `Axy`  | Volume slide      | Up by `x`, down by `y` — exactly one must be 0. **Retriggers the active note every tick** (audible click). Not available on CH3. Prefer instrument envelopes or `Cxx`. |
| `Bxx`  | Position jump     | Jump to order `xx`. |
| `Cxy`  | Set volume        | Set channel volume to `y`, **retriggers active note**. If `x != 0`, `x` is written to NR12 envelope bits. |
| `Dxx`  | Pattern break     | Jump to next order, start on row `xx`. |
| `Exx`  | Note cut          | Cut note after `xx` ticks. **Won't cut if `xx >= tempo`**. |
| `Fxx`  | Set tempo         | Set ticks-per-row. Alternating `Fxx` values gives fractional speeds (e.g. F04/F03 alternating = tempo 3.5). |

## Corpus usage (from `tests/analyze_effects.py`, 22 songs)

Sorted by usage frequency. `main` = pattern cells; `sub` = subpattern
cells. `w/note` = effect appears on a cell that also has a note.

| Effect | Total | main / sub | Top params | Notable channel skew |
|--------|-------|-----------|------------|---------------------|
| `Cxx`  | 6567  | 6545 / 22 | `C03 C04 C01 C07 C08 C0F C02` | CH1 heavy (3151), CH3 second (2258) |
| `4xy`  | 2603  | 2595 / 8  | `4C3 472 443 442 481 4A4 4C2` | CH3 heavy (1131); **91% on empty rows** |
| `0xy`  | 1933  | 1933 / 0  | `047 037 038 07B 07A 027`    | CH1 heavy (1162); 32% on empty rows (arps applied to already-playing notes) |
| `Fxx`  | 1857  | 1857 / 0  | `F03 F04 F02`                | **87% on CH4** — tempo controls parked on the noise channel |
| `Exx`  | 1855  | 1855 / 0  | `E01 E00 E04 E02 E03`        | CH3 heavy (754); 69% on empty rows |
| `2xx`  | 1154  | 1142 / 12 | `220 2FF 2F0 210 201`        | Roughly even across CH1/2/3; 70% on empty rows |
| `3xx`  | 551   | 551 / 0   | `308 330 30F 3FF 3F0`        | CH1/2/3 balanced; usually on cells with a note (the target) |
| `9xx`  | 503   | 435 / 68  | `940 980 900 9C0`            | CH1/2 only (unsurprisingly — CH3/4 uses are different) |
| `8xx`  | 416   | 416 / 0   | `8FF 8EF 8DF 8FD 8FE`        | Balanced across all channels |
| `Axy`  | 409   | 409 / 0   | `A01 A0F A02 A0C`            | CH2 heavy (249); **97% on empty rows** |
| `1xx`  | 96    | 86 / 10   | `102 101 104 103 105`        | CH3 leaning (37); usually with a note |
| `5xx`  | 65    | 65 / 0    | `566 555 544 533 522 511 500`| Only used in *SVL — Yyna*; almost entirely CH4 (65 uses on CH4) |
| `Bxx`  | 25    | 25 / 0    | `B00`                        | Rare position jumps |
| `7xx`  | 19    | 19 / 0    | `704`                        | Only in *SVL — Yyna* |
| `Dxx`  | 12    | 12 / 0    | `D01`                        | Only 3 songs, all D01 |
| `6xy`  | 0     |           | —                            | Nobody uses call-routine |

**Reading the skew columns is useful.** e.g., that `Fxx` sits on CH4 87% of
the time is a corpus convention: tempo changes go on the channel that
otherwise doesn't need effects.

## The row-scoped rule, applied

Any effect that shapes a *continuous* modulation (vibrato, arp, portamento,
duty morph, volume slide) must be repeated on every row that should carry
the modulation. There are two mechanisms:

1. **Repeat the effect cell** on each row. Fine for short (2–4 row) sustains.
   The `Axy`, `Exx`, `Fxx` corpus rows are almost entirely empty-note cells
   sitting after their trigger row.
2. **Put the modulation in a subpattern** (see § "Subpatterns"). Subpattern
   rows run per-tick, so a 6-row subpattern with `04y` on every row gives a
   continuous vibrato at 1-tick granularity without needing to touch the
   main tracker grid.

The tips section of the effect reference has hUGETracker-author-recommended
patterns worth internalizing:

- *"`A` stops the current instrument's envelope if one is active. `A00` is
  probably not desirable, so consider using it in a subpattern, so that it
  is only active for a single tick."* — the subpattern-first pattern for
  envelope shaping.
- *"Using `C` causes a click, so prefer baking the volume into the
  instrument when possible."* — don't reach for `Cxx` as an envelope tool.
- *"Vibrato using repeated `2xx` and `1xx` effects can give better results
  and more intricate/detailed vibrato than `4xy`, especially in subpatterns."*
- *"Notes without an instrument on their row can help with reducing noise,
  as the note isn't retriggered."* — for continued modulation without
  restarting the envelope.

## Subpatterns

A subpattern is a mini-tracker grid attached to an instrument (V6+ format).
Each subpattern row runs on **one tick** of the outer pattern row. If the
outer row has ticks-per-row=7 and the subpattern has 3 rows that loop
back, the loop runs 2⅓ times per outer row. Subpatterns loop back to row 0
automatically, or halt if a row jumps to itself.

Subpattern cells have three columns in the UI (`offset`, `jump`, `effect`).
On disk they use the same 17-byte `TCellV2` structure as main patterns:

- `note` field = the offset (encoded as `MIDDLE_NOTE + delta`, see below).
- `volume` field = **jump target** (0 = advance, N = jump to row N).
- `effect_code` / `effect_params` = the effect.

**Compiled subpattern length is 32 rows**, not 64 (`hUGETracker/src/codegen.pas:475-528`).
Rows 32..63 of the on-disk `TPattern` buffer are ignored by the code
generator; `hugecodec.subpatterns._place` refuses to write past row 31 to
avoid silent truncation surprises.

**Loop semantics** (verified against `codegen.pas:167-170` and corpus
audit at `tests/analyze_subpatterns.py`):

- Row 0 plays once when the note triggers.
- Rows 1..31 form the loop body.
- If row 31 has `volume = 0`, the codegen automatically inserts a
  jump-to-row-1, so subpatterns loop by default without any explicit jump.
- Anywhere in the subpattern, `volume = N` (1..31) makes that cell jump
  to row N *after* it plays. Common patterns:
  - `volume = 1` on the last used row of an arp → tight cycle
  - `volume = self_row` → halt (freeze on this cell). Used by FADE
    Microplastics *arp1* (jump-to-1 on row 5), Kekri *basso* (jump-to-9
    on row 9, halting).
- If the shape is shorter than 32 rows and doesn't set a jump, the
  auto-jump-to-row-1 still fires — but only after rows N+1..31 play
  (holding the pitch/effect from the last non-empty row). This is the
  bug that would silently break arpeggios if the constructor doesn't add
  an explicit loop jump.

### Offset encoding — `MIDDLE_NOTE = 36`

The subpattern `note` field is a signed offset expressed as
`MIDDLE_NOTE + delta`, where `MIDDLE_NOTE = 36` (defined in
`hUGETracker/src/constants.pas:139`, computed from `HIGHEST_NOTE=71` and
`LOWEST_NOTE=0`). So on disk:

| `note` value | UI display | Semantic |
|-------------|-----------|---------|
| `36`        | `+00`     | base note (no offset) |
| `37`        | `+01`     | +1 semitone |
| `48`        | `+12`     | +1 octave |
| `35`        | `-01`     | -1 semitone |
| `24`        | `-12`     | -1 octave |
| `0`         | `-36`     | -3 octaves (max negative) |
| `71`        | `+35`     | +35 semitones (max positive) |
| `90`        | `---`     | `NO_NOTE` (empty row) |

The tracker manual's phrasing *"positive number of semitones added to the
base note"* is misleading. Use `MIDDLE_NOTE` constant from
`hugecodec.format` when authoring subpatterns.

### Corpus subpattern shapes (from `tests/analyze_subpatterns.py`)

Of 38 enabled subpatterns across V6 corpus files:

- **16 percussion transients** (all CH4/noise): short subpatterns like
  `[+00, +00, +00, +00]` for hats (constant offset, envelope shapes the
  decay), or `[+00, -36, -36, +00]` for snares (pitch-drop transient).
- **10 arps** (mostly CH1/2 duty): 4–6-row offset cycles like
  `[+08, +17, +00, +20, +05, +12]` — chord-shape rotation.
- **6 timbre-morphs** (CH1/2 duty): 10–32 row subpatterns dominated by
  `9xy` cells cycling duty position mid-note. Tempest's `Kekri` uses this
  heavily.
- **3 plucks** (CH1/2 duty): 2-row `[+12, +00]` — octave-up blip on tick 0,
  base note thereafter. Adds a percussive attack to a sustained sound.
- **3 envelope-shape subpatterns** (mixed): `Cxy` steps on a few rows for
  manual ADSR-like release.

The `src/hugecodec/subpatterns.py` module provides constructors for these
shapes. Read that module for the canonical implementations.

## hugecodec misuse log (2026-08-11)

Concrete cautionary examples from my first pass on the Mother 3 love theme
variations. Left here so future sessions don't repeat them.

1. **Invented `E0x = "duty morph"`** based on seeing E00 appear on empty
   rows during sustained notes in the Pokémon Center arrangement. I never
   checked the effect reference. E is note-cut (cut after `xx` ticks).
   Wrote it into "diagnostics" as if verified. **Rule: never infer effect
   semantics from usage patterns — always cross-reference the manual, then
   confirm with corpus data.**
2. **Placed `4xy` vibrato on one row after each note** in var 5, expecting
   the effect to persist across the sustained tail. It fired for one row
   then stopped. Per the row-scoped rule, sustained vibrato needs `4xy` on
   every row of the sustain (or a subpattern).
3. **Used `Cxx` for manual release** in var 5, not knowing it retriggers
   the active note. 4 fresh attacks across the sustain instead of a smooth
   fade. Docs literally warn about this.
4. **Placed `07A` arpeggio on chord roots** in var 3, expecting the arp to
   continue for the whole held-note region. Fired one row, stopped. Same
   fix: repeat every row, or put it in the wave instrument's subpattern.
5. **Added redundant `F0B` to row 0** in `shared_cleanup` — song was
   already at tempo 11 (ticks-per-row=11 default). Pure cargo-cult.
6. **Kick lacked a transient** in var 4 because I built it as a static
   low-note noise instrument with no subpattern. Real GB kicks use a
   subpattern shifting pitch downward across the first few ticks.
7. **Ignored subpatterns entirely.** They're the primary shaping mechanism
   for anything more expressive than a flat linear envelope.

## Update protocol

When you use an effect for the first time in a new context (new channel,
new interaction with envelope, new subpattern position), verify the
semantic against `effect-reference.md` before writing. If the corpus
audit table above becomes stale (new songs added, new effects observed
being used in unexpected ways), re-run `python3 tests/analyze_effects.py`
and update the table.
