# Format notes

Everything here is derived from reading `song.pas` and `hugedatatypes.pas` in
`SuperDisk/hUGETracker` (branch `hUGETracker`), plus empirical validation
against `~/hugetracker-sample-songs/`.

## Header signature

- First 4 bytes: `Version: Int32` little-endian. Values seen in the wild:
  1, 3, 4, 5, 6. (V2 exists in the Pascal source but nothing in the corpus.
  V7 exists in current hUGETracker but no sample yet.)

## Enum sizing

Enums in `packed record` are **4 bytes** in FreePascal's default
`$MINENUMSIZE 4`. Not 1. This matters for every instrument field of type
`TInstrumentType`, `TSweepType`, `TStepWidth`. Empirical: TSongV5 header
alignment only worked with 4-byte enums (Chavez file, TicksPerRow lands at
offset 0x3B82 with value 7).

Range types (`0..15`, `0..7`, `0..3`, etc.) remain 1 byte — packed records
still shrink small subranges.

## ShortString

Pascal `ShortString` = 1 length byte + 255 data bytes = **256 bytes fixed**.
The bytes past `length` are undefined on write (garbage from the writer's
stack/heap). Round-trip fidelity is therefore **semantic**, not byte-exact.

## AnsiString

`TStream.ReadAnsiString` / `WriteAnsiString` = 4-byte length prefix + N data
bytes. Used for routine strings (V2+).

## Per-version layouts

Cell sizes:
- `TCellV1` (used in V1–V5): Note(4) + Instrument(4) + EffectCode(4) + Params(1) = **13 bytes**
- `TCellV2` (used in V6+): Note(4) + Instrument(4) + Volume(4) + EffectCode(4) + Params(1) = **17 bytes**

Pattern = 64 cells → 832 bytes (V1–V5) or 1088 bytes (V6+).

Instrument sizes (all include a 256-byte `Name` ShortString):
- `TInstrumentV1` (V1–V3): 304 bytes
- `TInstrumentV2` (V4–V5): 310 bytes (adds `NoiseMacro: array[0..5] of shortint` = 6 bytes)
- `TInstrumentV3` (V6+): 1385 bytes (drops `ShiftClockFreq`, adds `SubpatternEnabled: Boolean` + `Subpattern: TPatternV2`)

The 1385 figure matches Nick Faro's wiki writeup — his notes were describing
V6, not V1.

Wave sizes:
- `TWaveV1` (V1–V2): 33 bytes (`packed array[0..32] of Byte`) — the 33rd byte
  looks vestigial; corpus files have it consistently zeroed. Might have been a
  loop-point in an early design.
- `TWaveV2` (V3+): 32 bytes

Wave bank = 16 waves.

Instrument bank / collection:
- V1/V2: single `TInstrumentBankV1` = 15 flat instruments (channel-type
  determined by each instrument's `Type_` field)
- V3+: `TInstrumentCollection` = 45 instruments split into 3 banks of 15
  (Duty for CH1/CH2, Wave for CH3, Noise for CH4)

Song-level fields per version:
- V1: Version, Name, Artist, Comment, Instruments(15), Waves(V1), TicksPerRow, Patterns, OrderMatrix
- V2: + Routines (16 AnsiStrings after OrderMatrix)
- V3: promotes Instruments to Collection(45) and Waves to V2 (32-byte)
- V4: promotes instruments to V2 (adds NoiseMacro)
- V5: layout identical to V4; only difference is patterns are stored as
  `(key: int, cells: 832 bytes)` pairs instead of implicit `0..n-1` keys
- V6: adds TimerEnabled + TimerDivider between TicksPerRow and Patterns;
  promotes cells to V2 (adds Volume) and instruments to V3 (adds subpatterns)
- V7: TicksPerRow becomes `packed array[0..3] of Integer` (per-channel speed);
  otherwise identical to V6

Patterns section always starts with `Count: Int32`. For V1–V4, that's followed
by `Count` patterns with implicit keys 0..N-1. For V5+, each pattern is
prefixed by an `Int32` key (patterns can be sparse).

OrderMatrix: 4 arrays (one per channel), each `Length: Int32` followed by
`Length` `Int32` pattern-keys.

Routines (V2+): fixed 16 AnsiStrings after OrderMatrix.

## OrderMatrix semantics

Channel indices: 0 = CH1 (Duty1), 1 = CH2 (Duty2), 2 = CH3 (Wave), 3 = CH4 (Noise).
The value at `OrderMatrix[ch][i]` is a **pattern key**, i.e., an index into
`patterns.data` (V5+) or an implicit 0-based index (V1–V4).

## Note values

Not yet verified against the tracker. TODO: cross-reference with `constants.pas`
to nail down what `Note: Integer` values mean (empty/off vs specific pitches).
Chavez file has note value 90 for empty rows and note 51 for a specific pitch.

## Effect encoding

Same as OpenMPT/MOD family: hex nibble (0..F) for the effect type, packed byte
for the parameter. `Fxx` = set-speed (persistent, global). Full effect table
is documented in the hUGETracker manual —
https://superdisk.github.io/hUGETracker/. Consider embedding a quick-ref block
in future text-format output.

## V1 quirks (verified against `Junichi Masuda - Wild Pokemon Appear.uge`)

- `InitialVolume` values up to 63 appear in the file, exceeding the
  documented `TEnvelopeVolume = 0..15` range. Almost certainly V1 stored
  `InitialVolume` as a raw NR12-style byte (upper nibble = volume, lower
  nibble = envelope sweep) rather than the range-typed split V4+ uses. We
  preserve the raw byte; interpretation is the writer/UI's problem.
- Empty instrument slots still carry non-zero default field values on disk
  (initial_volume, sweep_direction, duty, etc.). "Is this slot used?" can't
  be inferred from field values alone — need to correlate with cell
  references (`Instrument` field in pattern cells) to know what's live.
- Type_ distribution into duty/wave/noise banks worked as expected: parsed
  V1 files place instruments correctly for their channel.

## Open questions
- V6 subpatterns inside instruments: what's the effective row-length limit?
  The record has a full 64-row `TPatternV2` but real usage might be much
  shorter — check via the tracker's subpattern editor.
- V7's per-channel `TicksPerRow[0..3]` — does the current UI expose per-CH
  speed, or is this future-proofing? Corpus has no V7 to check against.
- ShortString garbage bytes — does the tracker read past the length byte
  when re-opening its own files? If yes, we need to preserve them exactly
  for a byte-perfect round-trip. If no, semantic equality is enough.
- Pattern index space: 0-based with sparse keys in V5+. What's the practical
  max key? The Chavez file uses keys up to ~200 with 197 patterns — dense.
