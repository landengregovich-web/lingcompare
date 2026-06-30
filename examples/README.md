# LingCompare Example Corpus — Spanish & Portuguese

This folder contains a ready-to-use example corpus for exploring LingCompare before
applying it to your own data.

**Languages:** Castilian Spanish and European Portuguese — two closely related Romance
languages descended from Latin, with well-documented systematic sound correspondences.
They are close enough to produce many candidates, and different enough that the
correspondences are informative rather than trivial.

---

## Files

| File | Format | Description |
|---|---|---|
| `es_wordlist.csv` | Wordlist CSV | 52 Spanish words, IPA-transcribed |
| `pt_wordlist.csv` | Wordlist CSV | 52 Portuguese words, IPA-transcribed |
| `es_interlinear.txt` | Interlinear glossed text | 15 Spanish utterances with morpheme breakdowns |
| `pt_interlinear.txt` | Interlinear glossed text | 15 Portuguese utterances with morpheme breakdowns |

IPA transcriptions are broad phonemic representations; narrow phonetic detail and
allophony are not systematically encoded. The goal is a clear, instructive demo, not
an exhaustive phonological description.

---

## What to expect

### Lexicon / Cognates page

The tool will propose **54 candidate pairs**. A few things to look for:

**Obvious cognates (accept these to seed the feedback loop):**
- `dia/dia`, `sol/sol`, `floɾ/floɾ`, `boka/boka`, `komeɾ/komeɾ` — near-identical forms
- `kaβeθa/kaβesa` — head; same consonant frame, θ~s correspondence
- `pelo/pelu`, `ɡato/ɡatu`, `naɾis/naɾis` — only final vowel quality differs

**Informative correspondences to discover:**

| Spanish | Portuguese | Gloss | Correspondence |
|---|---|---|---|
| /notʃe/ | /nojte/ | night | tʃ ~ jt (Latin -CT-) |
| /otʃo/ | /ojtu/ | eight | tʃ ~ jt |
| /letʃe/ | /lejte/ | milk | tʃ ~ jt |
| /petʃo/ | /pejtu/ | chest | tʃ ~ jt |
| /oxo/ | /oʎu/ | eye | x ~ ʎ (Latin -LI-, -C'L-) |
| /oɾexa/ | /oɾeʎa/ | ear | x ~ ʎ |
| /ixo/ | /fiʎu/ | son | x ~ ʎ + initial f ~ ∅ |
| /muxeɾ/ | /muʎeɾ/ | woman | x ~ ʎ |
| /aɣwa/ | /aɡwa/ | water | ɣ ~ ɡ (intervocalic weakening) |
| /neɣɾo/ | /neɡɾu/ | black | ɣ ~ ɡ |

**Deliberate non-cognate pair:**
- `peɾo/kaw` (dog) — Spanish *perro* and Portuguese *cão* come from different Latin
  roots. The tool may not even propose this pair (the forms are too different), but if
  it does appear, it is a good example to reject.

**Recommended workflow:**

1. Accept the obvious identical/near-identical cognates first (~15 pairs).
2. Watch the systematicity scores update on the remaining candidates.
3. The pairs with `tʃ ~ jt` correspondence (night, eight, milk, chest) should now
   score higher — accept them.
4. The `x ~ ʎ` pairs (eye, ear, son, woman) should rise next — accept them.
5. Check the **systematic correspondences panel** at the bottom of the page; it
   summarises the patterns you have confirmed so far.

### Phonology page

Expected findings:
- Large shared inventory (~20 phonemes including all vowels and most consonants)
- Spanish-only: /θ/ (inter-dental fricative in Castilian *c/z*)
- Portuguese-only: /ʀ/ (uvular rhotic), /ʒ/, /ʃ/ as phonemes
- Both have /ʎ/, /ɲ/, /β/, /ð/, /ɣ/, /ɾ/

### Grammar page

Load the interlinear files on the **Load Corpora** page (paste or upload) to populate
the Grammar page. Both texts use these morpheme tags:

| Tag | Meaning | Example |
|---|---|---|
| `PL` | plural | `ɡato-s / cat-PL` |
| `3PL` | 3rd person plural agreement | `kome-n / eat-3PL` |
| `1SG` | 1st person singular agreement | `ew komu paw / 1SG eat.1SG bread` |
| `3SG` | fused 3rd singular | `eat.3SG` |

The tool will propose `PL ~ PL` (identity), `3PL ~ 3PL` (identity), and `1SG ~ 1SG`
(identity) as confirmed correspondences. Morpheme alignment shows the plural suffix
/-s/ is shared, while verb endings differ slightly (ES `-n` ~ PT `-m` for 3PL).

---

## Loading the corpus

### Lexical analysis only (fastest start)

1. Open the **Load Corpora** page.
2. Under **Corpus A**, expand **Wordlist CSV**, upload `es_wordlist.csv` or paste its
   contents.  Enter `Spanish` as the language name.
3. Under **Corpus B**, expand **Wordlist CSV**, upload `pt_wordlist.csv`.
   Enter `Portuguese`.
4. Click **Run Analysis**.

### Adding grammar analysis

On the same page, under each corpus, expand **Interlinear glossed text** and
upload or paste the corresponding interlinear file (`es_interlinear.txt` /
`pt_interlinear.txt`).  The wordlist and interlinear data are merged automatically —
you get the full 52-word lexical comparison *and* morpheme-level grammar analysis
from the interlinear texts at the same time.

**Note:** do not paste the interlinear file into the Wordlist CSV section — they use
different formats and the parser will report errors.

---

## IPA notes

The transcriptions use standard IPA symbols supported by PanPhon 0.20+:

- Spanish intervocalic stops are transcribed as fricatives/approximants: /b/→/β/,
  /d/→/ð/, /g/→/ɣ/ (this reflects common phonological description of Castilian).
- Portuguese /g/ is transcribed as /ɡ/ (U+0261, the IPA script-g, *not* regular
  ASCII `g` which PanPhon does not recognise).
- Nasal vowels and diphthongs are simplified to avoid PanPhon's limited coverage of
  pre-nasalised or combined diacritic segments.
- /r/ (Spanish trill, initial position) and /ɾ/ (tap, medial) are distinguished.
  Portuguese initial /r/ is transcribed as /ʀ/ (uvular) in words where it is shown
  as such (e.g. `ʀoʃu` "red").
