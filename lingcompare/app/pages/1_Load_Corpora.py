"""Load Corpora page — upload wordlists and/or interlinear text for N languages."""

from __future__ import annotations
import hashlib
import streamlit as st

from lingcompare.app.state import init_state, reset_state
from lingcompare.core.ingest_wordlist import parse as parse_wordlist
from lingcompare.core.ingest_interlinear import parse as parse_interlinear
from lingcompare.core.ingest_xlsx import parse as parse_xlsx
from lingcompare.core.ingest_docx import parse as parse_docx
from lingcompare.core.cognate_engine import run_pass_a, run_pass_b, run_all_pairs
from lingcompare.core.schema import Corpus

st.set_page_config(page_title="Load Corpora — LingCompare", layout="wide")
init_state()

st.title("Load Corpora")
st.markdown(
    "Add as many languages as you need. "
    "Each language can be loaded from a **wordlist** (CSV, Excel, Word) "
    "and/or **interlinear glossed text**. "
    "Use **Mass Compare** to see all pairs at once, or pick a pair here "
    "to analyse in the Phonology / Lexicon / Grammar pages."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _root_gloss(gloss: str) -> str:
    return gloss.lower().split(".")[0].split("-")[0].strip()


def _dedup_words(words):
    seen: dict[str, int] = {}
    kept = []
    for w in words:
        key = _root_gloss(w.gloss)
        if key not in seen:
            seen[key] = len(kept)
            kept.append(w)
        elif len(w.gloss) < len(kept[seen[key]].gloss):
            kept[seen[key]] = w
    return kept


def _merge_corpora(a: Corpus | None, b: Corpus | None, language_name: str) -> Corpus | None:
    if a is None and b is None:
        return None
    if a is None:
        return Corpus(language_name=language_name, words=_dedup_words(b.words),
                      gloss_glossary=b.gloss_glossary)
    if b is None:
        return Corpus(language_name=language_name, words=_dedup_words(a.words),
                      gloss_glossary=a.gloss_glossary)
    wl_roots = {_root_gloss(w.gloss) for w in a.words}
    extra = [w for w in b.words if _root_gloss(w.gloss) not in wl_roots]
    merged_glossary = {**a.gloss_glossary, **b.gloss_glossary}
    return Corpus(language_name=language_name, words=_dedup_words(a.words + extra),
                  gloss_glossary=merged_glossary)


def _corpus_hash(corpus: Corpus) -> str:
    content = str([(w.gloss, w.ipa) for w in corpus.words])
    return hashlib.md5(content.encode()).hexdigest()


@st.cache_resource
def _cached_pair(hash_a: str, hash_b: str, _ca, _cb):
    cands = run_pass_a(_ca, _cb)
    return run_pass_b(cands)


# ---------------------------------------------------------------------------
# Per-language panel
# ---------------------------------------------------------------------------

def _language_panel(idx: int) -> Corpus | None:
    """Render upload UI for one language slot. Returns Corpus or None."""
    key = f"lang_{idx}"

    lang_name = st.text_input(
        "Language name",
        key=f"{key}_name",
        placeholder=f"Language {idx + 1}",
    )

    with st.expander("Wordlist — CSV, Excel, or Word", expanded=True):
        st.caption("Two columns: **gloss** and **IPA**. Header row optional.")
        wl_upload = st.file_uploader(
            "Upload wordlist", type=["csv", "txt", "xlsx", "docx"],
            key=f"{key}_wl_file",
        )
        wl_paste = st.text_area(
            "…or paste CSV",
            key=f"{key}_wl_paste",
            height=100,
            placeholder="water,aɣwa\nfire,fweɣo",
        )

    with st.expander("Interlinear glossed text", expanded=False):
        st.caption("IPA:/GLOSS:/TRANS: blocks separated by blank lines.")
        il_upload = st.file_uploader(
            "Upload interlinear", type=["txt"],
            key=f"{key}_il_file",
        )
        il_paste = st.text_area(
            "…or paste interlinear",
            key=f"{key}_il_paste",
            height=100,
            placeholder="IPA:   aɣwa-s\nGLOSS: water-PL\nTRANS: waters",
        )

    # Parse wordlist
    wl_corpus: Corpus | None = None
    lname = lang_name.strip() or f"Language {idx + 1}"

    if wl_upload is not None:
        raw = wl_upload.read()
        name = wl_upload.name.lower()
        if name.endswith((".xlsx", ".xlsm", ".ods")):
            corpus, errors = parse_xlsx(raw, language_name=lname)
        elif name.endswith(".docx"):
            corpus, errors = parse_docx(raw, language_name=lname)
        else:
            corpus, errors = parse_wordlist(raw.decode("utf-8"), language_name=lname)
        if errors:
            for e in errors[:10]:
                st.error(str(e))
        else:
            st.success(f"{len(corpus.words)} words loaded.")
            wl_corpus = corpus
    elif wl_paste.strip():
        corpus, errors = parse_wordlist(wl_paste.strip(), language_name=lname)
        if errors:
            for e in errors[:10]:
                st.error(str(e))
        else:
            st.success(f"{len(corpus.words)} words loaded.")
            wl_corpus = corpus

    # Parse interlinear
    il_corpus: Corpus | None = None
    il_raw: str | None = None
    if il_upload is not None:
        il_raw = il_upload.read().decode("utf-8")
    elif il_paste.strip():
        il_raw = il_paste.strip()

    if il_raw is not None:
        corpus, errors = parse_interlinear(il_raw, language_name=lname)
        if errors:
            for e in errors[:10]:
                st.error(str(e))
        else:
            n_morph = sum(len(w.morphemes) for w in corpus.words)
            st.success(f"{len(corpus.words)} words, {n_morph} morphemes loaded.")
            il_corpus = corpus

    return _merge_corpora(wl_corpus, il_corpus, lname)


# ---------------------------------------------------------------------------
# Language panels
# ---------------------------------------------------------------------------

st.divider()

# Ensure lang_count is at least 2
if st.session_state.lang_count < 2:
    st.session_state.lang_count = 2

# Ensure corpora list is long enough
while len(st.session_state.corpora) < st.session_state.lang_count:
    st.session_state.corpora.append(None)

for i in range(st.session_state.lang_count):
    col_title, col_remove = st.columns([9, 1])
    with col_title:
        st.subheader(f"Language {i + 1}")
    with col_remove:
        if i >= 2 and st.button("✕", key=f"remove_{i}", help="Remove this language"):
            st.session_state.corpora.pop(i)
            st.session_state.lang_count -= 1
            # Invalidate any pair results that referenced this index
            st.session_state.pair_results = {}
            st.rerun()

    result = _language_panel(i)
    if result is not None:
        if i < len(st.session_state.corpora):
            st.session_state.corpora[i] = result
        else:
            st.session_state.corpora.append(result)

    st.divider()

# Add language button
if st.button("＋ Add another language"):
    st.session_state.lang_count += 1
    st.rerun()

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

loaded = [c for c in st.session_state.corpora if c is not None]
n_loaded = len(loaded)

if n_loaded >= 2:
    st.subheader("Analyse")

    lang_names = [c.language_name for c in st.session_state.corpora if c is not None]
    corpus_list = [c for c in st.session_state.corpora if c is not None]

    col_a, col_b, col_run, col_all = st.columns([2, 2, 2, 2])

    with col_a:
        sel_a = st.selectbox("Language A", options=range(n_loaded),
                             format_func=lambda i: lang_names[i], key="sel_a")
    with col_b:
        options_b = [i for i in range(n_loaded) if i != sel_a]
        sel_b = st.selectbox("Language B", options=options_b,
                             format_func=lambda i: lang_names[i], key="sel_b")

    with col_run:
        st.write("")  # vertical align
        if st.button("Analyse this pair", type="primary", use_container_width=True):
            ca, cb = corpus_list[sel_a], corpus_list[sel_b]
            with st.spinner("Aligning…"):
                corrs, cands = _cached_pair(
                    _corpus_hash(ca), _corpus_hash(cb), ca, cb
                )
            st.session_state.corpus_a = ca
            st.session_state.corpus_b = cb
            st.session_state.candidates = cands
            st.session_state.correspondences = corrs
            st.session_state.pass_a_done = True
            st.session_state.pass_b_done = True
            st.success(f"{len(cands)} candidate pair(s). Go to **Lexicon / Cognates**.")

    with col_all:
        st.write("")
        if st.button("Analyse all pairs", use_container_width=True):
            with st.spinner(f"Running {n_loaded*(n_loaded-1)//2} pair(s)…"):
                results = run_all_pairs(corpus_list)
            st.session_state.pair_results = results
            # Also set the selected pair as active
            corrs, cands = results[(min(sel_a, sel_b), max(sel_a, sel_b))]
            st.session_state.corpus_a = corpus_list[sel_a]
            st.session_state.corpus_b = corpus_list[sel_b]
            st.session_state.candidates = cands
            st.session_state.correspondences = corrs
            st.session_state.pass_a_done = True
            st.session_state.pass_b_done = True
            n_pairs = len(results)
            st.success(f"{n_pairs} pair(s) analysed. See **Mass Compare** for the overview.")

else:
    st.info("Load at least two languages to run analysis.")

# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

st.divider()
if st.button("Clear everything & start over"):
    reset_state()
    st.rerun()
