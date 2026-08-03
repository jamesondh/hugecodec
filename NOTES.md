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

### Wave-channel sample interpretation

Each wave is 32 samples of 4-bit resolution. On the Game Boy wave channel the
32-sample cycle repeats at the note frequency, so a DFT of the 32 samples
reveals the harmonic partials heard above that fundamental.

Practical consequences (see `waves.py`):
- Only bins 1..16 are addressable (Nyquist for N=32).
- A wave with dominant energy at bin K sounds K× above the tracker note.
  This is why hUGETracker "sine" waves that actually contain two cycles of a
  sine (peak at bin 2) play an octave higher than the note grid suggests.

### What actually works: close-bin dyads

FADE's `minor` / `major` / `fourth` waves in *Microplastics in the Air* place
energy at two adjacent bins (5:6, 4:5, 3:4) with 90%+ spectral purity. When
played at a tracker note, these produce **two audible pitches** at K·f and
(K+1)·f — an interval of (K+1)/K = 6/5 (m3), 5/4 (M3), or 4/3 (P4). The ear
localizes both bins as distinct tones because they're close together and
dominate the spectrum. This is the only wave-channel chord-illusion
technique that reliably reads as an interval.

`interval_wave()` in the library exposes this for the four adjacent-bin
intervals: m3, M3, P4, P5. Wider ratios (m6, M6, m7, M7, P8) exist
mathematically but on 32 samples × 4 bits they don't survive as intervals —
they collapse into a single colored timbre.

### What doesn't work: "chord waves" at scattered high bins

The obvious next idea is to build a full minor triad by placing partials at
bins 10:12:15 (JI ratios 1:6/5:3/2). This does not work. The wave has no
energy at bins 1..9, so the ear applies the missing-fundamental illusion,
hears the tracker note (bin 1) as the perceived root, and treats 10/12/15
as upper harmonics of that single pitch — not as three simultaneous voices.
The audible result is a rooted single note with a bright, slightly
inharmonic color. Codex reviewed this and concurred: a 32-sample periodic
waveform is one pitched source, not three, and no cleverness with bin
placement changes that.

The same failure mode applies to any "triad wave" (4:5:6, 6:8:9, etc.) and
any "7th chord wave" (4:5:6:7, 10:12:15:9, etc.). They're not chords —
they're timbral color sets on one pitch. This is why the library exposes
`from_harmonics()` as an honest low-level additive designer but does NOT
ship `triad_wave()` or `seventh_wave()` constructors.

### Future exploration: harmonic color sets

Even though these multi-bin designs aren't chords, they're still a
legitimate design space for **novel timbres** — Game Boy sounds that don't
come out of the standard pulse/triangle/noise palette. FADE's wave-channel
work is evidence that pushing outside "sine, square, sawtooth" pays off
musically. Potential directions worth pressuring:

- **Formant-like designs.** Cluster energy in a narrow band of bins (say
  6:7:8) to simulate a vowel formant. Different clusters = different
  vowels.
- **Inharmonic timbres.** Place partials at ratios that don't sit on the
  natural harmonic series — e.g. 7:11:13. Bell-like or metallic textures.
- **Register shifters.** A wave dominated by bin 4 sounds two octaves
  above the tracker note. Combine with a subtle lower partial for a
  "hollow octave" effect (see FADE's bank 9 "Pointy" — bins 1:2, a natural
  octave doubler).
- **Missing-fundamental exploits.** The illusion that ruins the "minor
  triad" idea is a *feature* if you use it deliberately — a wave with
  energy only at 4:6:8 (all multiples of 2) will imply a phantom
  fundamental one octave below the tracker note. Cheap sub-bass.
- **Vector-synthesis-style morphing.** Two waves swapped mid-note via
  subpattern instrument changes would let you scan through timbral color
  sets over time.

The `from_harmonics()` API is enough to prototype any of these. The
question isn't "can we build it" but "which set of these deserves a named
constructor with a claim attached." Postponing until we have real
side-by-side audio comparisons on hardware.

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
