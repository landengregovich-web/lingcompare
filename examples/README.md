# LingCompare Example Corpus — Spanish, Portuguese & French

This folder contains a ready-to-use example corpus for exploring LingCompare before
applying it to your own data.

**Languages:** Castilian Spanish, European Portuguese, and French — three closely
related Romance languages descended from Latin. They share a large common vocabulary
but have diverged enough to produce informative sound correspondences. Using all three
together is the recommended way to try out the **Mass Compare** feature.

---

## Files

| File | Format | Description |
|---|---|---|
| `es_wordlist.csv` | Wordlist CSV | 52 Spanish words, IPA-transcribed |
| `pt_wordlist.csv` | Wordlist CSV | 52 Portuguese words, IPA-transcribed |
| `fr_wordlist.csv` | Wordlist CSV | 54 French words, IPA-transcribed |
| `es_interlinear.txt` | Interlinear glossed text | 15 Spanish utterances with morpheme breakdowns |
| `pt_interlinear.txt` | Interlinear glossed text | 15 Portuguese utterances with morpheme breakdowns |
| `fr_interlinear.txt` | Interlinear glossed text | 15 French utterances with morpheme breakdowns |

IPA transcriptions are broad phonemic representations; narrow phonetic detail and
allophony are not systematically encoded.

---

## Quick start — Mass Compare (all three languages)

1. Open the **Load Corpora** page.
2. Under **Language 1**, upload `es_wordlist.csv` and `es_interlinear.txt`. Name it `Spanish`.
3. Click **＋ Add another language**.
4. Under **Language 2**, upload `pt_wordlist.csv` and `pt_interlinear.txt`. Name it `Portuguese`.
5. Click **＋ Add another language**.
6. Under **Language 3**, upload `fr_wordlist.csv` and `fr_interlinear.txt`. Name it `French`.
7. Click **Analyse all pairs**.
8. Go to **Mass Compare** — you will see a 3×3 similarity matrix and the full concept table.

---

## What to expect

### Mass Compare page

The similarity matrix should show Spanish–Portuguese as the most similar pair (~75–80%),
with French somewhat more distant from both (~55–65%). This reflects actual genetic
distance — Spanish and Portuguese diverged later and more locally than they each did
from French.

In the concept table, filter to concepts present in all 3 languages and look for:

| Concept | Spanish | Portuguese | French | Pattern |
|---|---|---|---|---|
| night | notʃe | nojte | nwi | tʃ ~ jt ~ ∅ (Latin -CT-) |
| eight | otʃo | ojtu | wit | tʃ ~ jt ~ t |
| milk | letʃe | lejte | lɛ | tʃ ~ jt ~ ∅ |
| fire | fweɣo | foɡu | fø | Latin FOCUS |
| son | ixo | fiʎu | fis | Latin FILIUS |
| ear | oɾexa | oɾeʎa | ɔʁɛj | Latin AURICULA |
| water | aɣwa | aɡwa | o | Latin AQUA |

### Pairwise — Spanish vs Portuguese

~54 candidate pairs. The most informative correspondences:

| Spanish | Portuguese | Gloss | Correspondence |
|---|---|---|---|
| /notʃe/ | /nojte/ | night | tʃ ~ jt (Latin -CT-) |
| /oxo/ | /oʎu/ | eye | x ~ ʎ (Latin -C'L-) |
| /aɣwa/ | /aɡwa/ | water | ɣ ~ ɡ (intervocalic weakening) |
| /ixo/ | /fiʎu/ | son | x ~ ʎ + f ~ ∅ |

### Pairwise — Spanish vs French / Portuguese vs French

French has undergone more extensive sound changes from Latin than Iberian Romance,
so correspondences are less regular but still detectable:

- Latin F: ES /fweɣo/, PT /foɡu/, FR /fø/ — initial f preserved, vowel very different
- Latin -CT-: ES /tʃ/, PT /jt/, FR silent (e.g. *nuit* < NOCTEM — the /kt/ disappeared entirely)
- Definite article: ES *el/la*, PT *o/a*, FR *le/la* — all from Latin ILLE/ILLA

### Phonology page

Spanish–Portuguese:
- Shared: most consonants, five-vowel core
- ES only: /θ/ (Castilian *c/z*)
- PT only: /ʀ/, /ʒ/, /ʃ/ as phonemes

Spanish–French / Portuguese–French:
- French has more front rounded vowels: /y/, /ø/, /œ/
- French has uvular /ʁ/ vs Iberian /r/, /ɾ/
- French has /ʒ/ and /ʃ/ as prominent phonemes

### Grammar page

Load the interlinear files to populate the Grammar page. The three texts share these
morpheme tags:

| Tag | Meaning | ES example | PT example | FR example |
|---|---|---|---|---|
| `PL` | plural | `ɡato-s / cat-PL` | `ɡatu-s / cat-PL` | (zero marking) |
| `3PL` | 3rd pl. agreement | `kome-n / eat-3PL` | `kome-m / eat-3PL` | `manʒ / eat.3PL` |
| `1SG` | 1st sg. | `ʝo / 1SG` | `ew / 1SG` | `ʒə / 1SG` |
| `3SG` | fused 3rd sg. | `kome / eat.3SG` | `kome / eat.3SG` | `manʒ / eat.3SG` |

French note: French spoken plurals are usually not phonemically marked on nouns
(`chat` and `chats` are both /ʃa/). The interlinear uses `hand.PL`, `bird.PL` etc.
to indicate grammatical plurality even when the noun form is unchanged. Verb 3SG and
3PL are also identical in many French verbs (e.g. *mange/mangent* both = /manʒ/).
The article alternation (`le/la` → `les`, `le` → `l-` before vowels) is the main
phonemic marker of plurality.

---

## IPA notes

- Spanish intervocalic stops are transcribed as approximants: /b/→/β/, /d/→/ð/, /g/→/ɣ/.
- All three languages use /ɡ/ (U+0261, IPA script-g, **not** ASCII `g`).
- French nasal vowels (/ɑ̃/, /ɔ̃/, /ɛ̃/) are written as vowel+nasal sequences (/an/, /on/, /ɛn/)
  to avoid combining diacritics that PanPhon does not handle.
- French /ʁ/ (uvular fricative) is used throughout; this is distinct from Spanish /r/ (trill)
  and /ɾ/ (tap) and Portuguese /ʀ/ (uvular trill).
- French /ø/, /œ/, /y/ are front rounded vowels; PanPhon fully supports them.
