<!-- hand-generated from src/hugecodec/presets.py — refresh via `hugecodec audition list` -->
# Preset hex sheet — paste into hUGETracker for A/B testing

Every preset is **32 hex chars = 32 nibbles = one wave-channel wave**. Paste directly
into hUGETracker's **HexWaveEdit** box and preview at **C-5**. Then generate the
matching WAV via `hugecodec audition render <name> --out /tmp/<name>.wav --note C5`.

**Note-name convention.** hUGETracker's `C-5` = 130.55 Hz, two octaves below scientific
pitch. `--note C5` and `--note C-5` both work.

**Ears-verdict labels** appear in the section headers. F1 = ship-ready dyads. F2 =
tinny colors. A-D legacy = colored bright tones, no chord percept. E-H = exploratory.
See `NOTES.md` for the adjacency rule and the reasoning behind these classifications.

---

## F1 · Reinforced dyads (ears-confirmed, ship-ready)

Codified octave-doubled-dyad recipe via `interval_wave_reinforced()`. Ears-confirmed
as clean adjacent-bin dyads — cleaner than FADE's own hand-shaped versions in
listening tests.

### reinforced-m3   —   bins 5:6 + 10:12 (m3 dyad + octave doubling)

    8fb7329db64779a6795688b9426dc840

### reinforced-M3   —   bins 4:5 + 8:10

    8fe96227bca647868978b95348dd9610

### reinforced-P4   —   bins 3:4 + 6:8

    7efc9632479aba657a954568bdc96301

---

## F2 · Extended adjacent-bin dyads (tinny colors, not clear dyads)

The adjacency rule predicted these should read as dyads. Ears confirmed they do
NOT — they sound tinny/interesting rather than distinctly two-pitched. Kept for
color reference; not clear enough to promote into `interval_wave()`.

### dyad-6-7   —   septimal minor third (ratio 7:6, ~267 cents)

    8fc318ea438b96688799647cb517ec30

### dyad-7-8   —   septimal major second (ratio 8:7, ~231 cents)

    8f915db34bb658978867a944bc42ae60

### dyad-8-9   —   major second / whole tone (ratio 9:8, ~204 cents)

    7f61ad43bb46a867889759b44cb25e90

### dyad-9-10   —   minor whole tone (ratio 10:9, ~182 cents)

    7f33e81ab37b66987769948c45e71cc0

### dyad-10-11   —   undecimal neutral second (ratio 11:10, ~165 cents)

    7f17f26e36c56a7788859a39c19d08e0

---

## A (legacy) · Bright colored tones — no chord percept

Originally shipped as "dom7 flavor." Listening tests confirmed no chord percept
survives fusion. Retained as timbral reference.

### dom7-narrow   —   bins 4:5:6:7, natural harmonic series

    8fe7248988997578878a8667867bd810

### dom7-wide   —   bins 8:10:12:14, same shape one octave up

    7f187a67789577e07f188a67789577e0

### dom7-rolloff   —   bins 4:5:6:7 with 1/n amp decay

    8ff8337889a97567889a8656778cc700

---

## B (legacy) · High-shimmer tones — no chord percept

Originally shipped as "maj7." Ears-confirmed WORST of A-D because bin 15 sits so
far from the triad body.

### maj7-just — 8:10:12:15

    7f2789685c4a3bb17e44c5b3a79678d0

### maj7-leadingtone-hint — 8:10:12:15, 7th at 40%

    7f2698766b694ac07f35b694998769d0

### maj7-open — 4:5:6 + bin 15 at 60%

    7fea134b9a69785689a7869564bce510

---

## C (legacy) · Low-cluster tones — no chord percept

### min7-truncated — 10:12:15 (minor triad ratios, upper register)

    8e0b975c4a3e18c28d37e1c5b3a864f1

### min7-septimal — 6:7:9:11 (septimal + 11-limit cluster)

    7f7477aa5679b54b84ba4689a5588b80

### min7-compressed — 5:6:7:9 (tight low-harmonic cluster)

    8fb4478aa659858b847a76a95578bb40

---

## D (legacy) · Consecutive-bin cluster — no chord percept

### dim7-septimal — 5:6:7:8 (dense unstable timbre)

    8fc338a88875799788668a878757cc30

---

## E · Register shifters

### octave-up-sine — bin 2 only, sine one octave up

    8adefeda852101257adefeda85210125

### thickener — bins 2:3:4:5 (no bin 1); warmth adder

    8dfda656887557888778aa8789a95202

---

## F · P8 fused octave doubler

### p8 — bins 1:2, octave-doubled tracker note

    8aceffedca8766677899987532100135

---

## G · Formant / vowel clusters

Three-adjacent-bin narrow bands. Ears-confirmed: **formant-mid** is the strongest.

### formant-low — bins 6:7:8 (hollow / reedy)

    8fa23bc7578789758a867878a834cd50

### formant-mid — bins 7:8:9 (nasal / most 'formant'-sounding)

    8f817d847988867a857987867b727e80

### formant-high — bins 8:9:10 (bright nasal)

    7f52cb37a77779857a76888858c43da0

### formant-low-rolloff — bins 6:7:8 with amp decay

    8fb328da5569a9548ba6569aa527dc40

---

## H · Inharmonic metallic — ears-confirmed STRONGEST exploratory category

Coprime-prime clusters, no natural-harmonic ratios. Bell-like, genuinely alien
timbres. Room to explore more sets.

### metallic-7-11-13 — three coprime primes, high-anchored

    8f3957d646d7593f80c6a829b928a6c0

### metallic-5-7-11 — coprime primes, warmer low end

    8f9654aa5aa4569f8069ab55a55ba960

### metallic-3-7-11 — anchored low, more fundamental presence

    8d8897a606a7988d82776859f9586772
