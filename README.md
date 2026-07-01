# LingCompare

An interactive Streamlit application for comparing linguistic corpora across phonology, lexicon, and grammar. Supports pairwise comparison of two languages or **mass comparison of any number of languages simultaneously**.

LingCompare **proposes** candidate correspondences with confidence scores and full evidence breakdowns. It does not assert truth — every candidate is a hypothesis for you to accept, reject, or leave pending.

**Live demo:** https://lingcompare.streamlit.app

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

### Run

**Windows:**

```
run.bat
```

**All platforms:**

```
python -m streamlit run lingcompare/app/Home.py
```

---

## Workflow

### 1 — Load Corpora

Add as many languages as you need using the **＋ Add another language** button. Each language slot accepts:

- A **wordlist** (CSV, Excel `.xlsx`, or Word `.docx`)
- An **interlinear glossed text** (`.txt`)
- Or both — they are merged automatically, with the wordlist taking priority

After loading, two buttons are available:

- **Analyse this pair** — fast, runs only the selected A/B pair
- **Analyse all pairs** — runs every N×(N−1)/2 combination at once; required for Mass Compare

### 2 — Phonology

Side-by-side phoneme inventory comparison for the active language pair. Shared phonemes, divergent phonemes, and natural-class breakdowns.

### 3 — Lexicon / Cognates

The main pair-level review page. Each proposed word pair shows:

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

Summary statistics, systematic correspondence table, accepted pairs preview, and export buttons (CSV and JSON).

### 6 — Mass Compare *(N-language)*

Overview page when three or more languages are loaded:

- **Similarity matrix** — N×N heatmap showing average phonetic similarity between every pair (green = more similar, red = more divergent)
- **Set active pair** — pick any two languages to drive the Phonology / Lexicon / Grammar pages
- **Concept table** — one row per concept (gloss), one column per language, IPA in each cell. A slider filters down to concepts shared across at least K languages — useful for spotting pan-family cognate sets

---

## Input formats

### Wordlist

Minimum two columns: **gloss** and **IPA transcription**. Header row is auto-detected. Accepted formats:

| Format | Notes |
|---|---|
| CSV / TXT | Comma- or tab-separated |
| Excel (`.xlsx`) | First worksheet used; named columns detected automatically |
| Word (`.docx`) | Table layout preferred; tab/comma-delimited paragraphs as fallback |

Column aliases recognised for the gloss column: `gloss`, `word`, `translation`, `meaning`, `english`, `form`, `entry`.
Column aliases recognised for the IPA column: `ipa`, `ipa_form`, `phonetic`, `transcription`, `pronunciation`.

Example CSV:

```
gloss,IPA
water,aɣwa
hand,mano
fire,fweɣo
```

An optional third column (`breakdown`, `morphemes`, etc.) accepts a morpheme breakdown string:

```
gloss,IPA,breakdown
waters,aɣwas,aɣwa-s
```

### Interlinear glossed text

Blocks separated by blank lines. Each block has:

```
IPA:   aɣwa-s   kela
GLOSS: water-PL big
TRANS: the big waters
```

- `IPA:` — space-separated words; hyphens separate morphemes within a word
- `GLOSS:` — matching space-separated words; hyphens separate gloss tags. Fused forms use `.` notation: `eat.3SG`
- `TRANS:` — free translation of the whole utterance (optional; used as gloss only for single-word blocks)

Word count and morpheme count must match between IPA and GLOSS lines per block. Validation errors are shown per-block without stopping the rest of the parse.

When a wordlist and interlinear are both loaded for the same language, they are merged: wordlist entries take priority, and only interlinear words whose root gloss is not already covered are added.

---

## Scoring

Five factors, each in [0, 1], combined as a weighted sum:

| Factor | Weight | What it measures |
|---|---|---|
| Phonetic | 35% | 1 − normalised NW alignment distance |
| Systematicity | 35% | How well the alignment fits attested cross-corpus sound correspondences |
| Gloss | 15% | Semantic similarity of the word glosses |
| Typology | 10% | Cross-linguistic naturalness of each implied sound change |
| Inventory | 5% | Fraction of target phonemes present in the target language's inventory |

The **Pass B fast score** (used for interactive sorting) is a simpler two-factor combination of phonetic distance and systematicity bonus. The full five-factor score appears in the evidence panel and exports.

---

## Architecture

```
lingcompare/
  lingcompare/
    core/
      schema.py               Phoneme, Morpheme, Word, Corpus dataclasses
      ingest_wordlist.py      CSV / TXT parser → Corpus
      ingest_xlsx.py          Excel parser → Corpus
      ingest_docx.py          Word document parser → Corpus
      ingest_interlinear.py   Block-format IGL parser → Corpus
      phon_align.py           Needleman-Wunsch + PanPhon distances
      phon_inventory.py       Inventory extraction and comparison
      cognate_engine.py       Pass A (gloss-anchored alignment) + Pass B (systematicity)
                              + run_all_pairs() for N-language mass comparison
      gloss_match.py          Cross-corpus gloss-tag correspondence proposals
      morph_typology.py       Morpheme position-distribution comparison
      scoring.py              Five-factor evidence combination
      export.py               CSV and JSON serialisation
    app/
      Home.py                 Entry point and navigation
      state.py                Session state schema (single-pair + multi-language)
      pages/
        1_Load_Corpora.py     Dynamic N-language loader
        2_Phonology.py        Inventory comparison
        3_Lexicon_Cognates.py Candidate review with accept / reject
        4_Grammar.py          Morphological tag correspondence
        5_Report.py           Summary and export
        6_Mass_Compare.py     N-language similarity matrix and concept table
  examples/
    es_wordlist.csv           Spanish Swadesh + core vocabulary (52 words, IPA)
    pt_wordlist.csv           Portuguese parallel (52 words, IPA)
    es_interlinear.txt        Spanish interlinear glossed text (15 utterances)
    pt_interlinear.txt        Portuguese parallel
  tests/
    fixtures/                 Sample wordlists and interlinear texts
    test_*.py                 186 tests; one module per core module
```

---

## Running tests

```
cd lingcompare
python -m pytest
```

All tests are pure Python — no Streamlit runtime, no network access, no API keys.

---

## No AI at runtime

LingCompare uses no language models or external APIs. All analysis is deterministic:

- Phonetic alignment: Needleman–Wunsch with PanPhon feature vectors
- Gloss matching: RapidFuzz edit distance
- Sound change plausibility: hardcoded table of ~40 attested historical changes
- Scoring: fixed weighted formula

Same input always produces the same output.

---

## Limitations and scope

- **Proposal only.** No automatic cognate judgements are made. Every output is a scored hypothesis.
- **Wordlist-level alignment.** Subword phonology (tone, vowel harmony, suprasegmentals) is not modelled.
- **No phylogenetic inference.** Correspondences show *what* is systematic; they do not reconstruct proto-forms or estimate divergence times.
- **IPA dependency.** All phonological analysis requires IPA transcriptions. Romanised input is not supported.
- **PanPhon feature coverage.** Phonemes not in PanPhon's feature table (e.g. clicks, some rare affricates) are flagged as validation errors and excluded from alignment.
- **English gloss labels.** The gloss-matching and morpheme-tag systems assume glosses are written in English. Other metalanguages require adjusting the alias tables in `ingest_xlsx.py`.
