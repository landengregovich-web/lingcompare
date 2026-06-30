# LingCompare

A local, interactive Streamlit application for comparing two linguistic corpora across phonology, lexicon, and grammar.

LingCompare **proposes** candidate correspondences with confidence scores and full evidence breakdowns. It does not assert truth — every candidate is a hypothesis for you to accept, reject, or leave pending.

---

## Quick start

### Prerequisites

- Python 3.10 or later
- [PanPhon](https://github.com/dmort27/panphon) 0.20+

**Windows note:** if you are on Python 3.14 + Windows, PanPhon's feature table may fail to load due to a UTF-8 encoding bug. Open `panphon/featuretable.py` in your site-packages and change all `open()` calls that read the `.csv` files to include `encoding="utf-8"`.

### Install

```
cd lingcompare
pip install -e .
```

Or install dependencies manually:

```
pip install panphon>=0.20 rapidfuzz>=3.0 streamlit>=1.30 pandas>=2.0
```

### Run

**Windows:**

```
run.bat
```

**All platforms:**

```
python -m streamlit run lingcompare/app/Home.py
```

Or, after `pip install -e .`:

```
lingcompare
```

---

## Workflow

### 1 — Load Corpora

Upload or paste data for two languages. Both corpora must be loaded before analysis begins.

After loading, click **Run Analysis** to:
- Pass A: align word pairs that share a gloss (semantic anchoring)
- Pass B: detect systematic sound correspondences across the candidate set

### 2 — Phonology

Side-by-side phoneme inventory comparison. Shared phonemes, divergent phonemes, and natural-class breakdowns.

### 3 — Lexicon / Cognates

The main review page. Each proposed word pair shows:
- Phonetic alignment (Needleman–Wunsch, PanPhon feature-weighted)
- Per-column typological plausibility of the implied sound change
- Full evidence breakdown across five factors (see Scoring below)
- Which systematic correspondences support or penalise this pair

Use **Accept / Reject** to give feedback. Every decision immediately re-runs Pass B and updates all candidate scores.

### 4 — Grammar

Proposed gloss-tag correspondences (e.g. `PL` ↔ `PLUR`) derived from interlinear text. Confirm or reject each mapping. For confirmed pairs, see:
- Morpheme-level phonetic alignment
- Position-distribution typology (prefix / suffix / infix / root)

### 5 — Report

Summary statistics, systematic correspondence table, accepted pairs preview, and three export buttons.

---

## Input formats

### Wordlist CSV

Minimum two columns: **gloss** and **IPA transcription**. Header is auto-detected.

```
gloss,IPA
water,aɣwa
hand,mano
fire,fweɣo
```

The separator can be comma or tab. A language-name column is optional — the file name is used as the default language name.

### Interlinear glossed text

Blocks separated by blank lines. Each block has:

```
IPA:   aɣwa-s
GLOSS: water-PL
TRANS: waters
```

- `IPA:` — space-separated words; hyphens separate morphemes within a word
- `GLOSS:` — matching space-separated words; hyphens separate gloss tags
- `TRANS:` — free translation (used as the word's gloss; optional)

Word count and morpheme count must match between IPA and GLOSS lines. Validation errors are shown per-block without stopping the rest of the parse.

---

## Scoring

Five factors, each in [0, 1], combined as a weighted sum:

| Factor | Weight | What it measures |
|---|---|---|
| Phonetic | 35% | 1 − normalised NW alignment distance |
| Systematicity | 35% | How well the alignment fits attested cross-corpus sound correspondences |
| Gloss | 15% | Semantic similarity of the word glosses (or confirmed tag coverage) |
| Typology | 10% | Cross-linguistic naturalness of each implied sound change |
| Inventory | 5% | Fraction of target phonemes present in target language's inventory |

The **Pass B fast score** (used for interactive sorting) is a simpler two-factor combination of phonetic distance and systematicity bonus; the full five-factor score appears in the evidence panel and exports.

---

## Architecture

```
lingcompare/
  lingcompare/
    core/
      schema.py             Phoneme, Morpheme, Word, Corpus dataclasses
      ingest_wordlist.py    CSV parser → Corpus
      ingest_interlinear.py Block-format IGL parser → Corpus
      phon_align.py         Needleman-Wunsch + PanPhon distances
      phon_inventory.py     Inventory extraction and comparison
      cognate_engine.py     Pass A (gloss-anchored alignment) + Pass B (systematicity)
      gloss_match.py        Cross-corpus gloss-tag correspondence proposals
      morph_typology.py     Morpheme position-distribution comparison
      scoring.py            Five-factor evidence combination
      export.py             CSV and JSON serialisation
    app/
      Home.py               Entry point and navigation
      state.py              Session state schema and helpers
      pages/
        1_Load_Corpora.py
        2_Phonology.py
        3_Lexicon_Cognates.py
        4_Grammar.py
        5_Report.py
  tests/
    fixtures/               Sample wordlists and interlinear texts
    test_*.py               One test module per core module
```

---

## Running tests

```
cd lingcompare
python -m pytest
```

All tests are pure Python (no Streamlit runtime needed).

---

## Limitations and scope

- **Proposal only.** No automatic cognate judgements are made. Every output is a scored hypothesis.
- **Wordlist-level alignment.** Subword phonology (tone, vowel harmony, suprasegmentals) is not modelled.
- **No phylogenetic inference.** Correspondences show *what* is systematic; they do not reconstruct proto-forms or estimate divergence times.
- **IPA dependency.** All phonological analysis requires IPA transcriptions. Romanised input is not supported.
- **PanPhon feature coverage.** Phonemes not in PanPhon's feature table (e.g. clicks, some rare affricates) are flagged as validation errors and excluded from alignment.
