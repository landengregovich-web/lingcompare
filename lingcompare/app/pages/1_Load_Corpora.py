"""Load Corpora page — upload or paste wordlists and/or interlinear text."""

from __future__ import annotations
import hashlib
import streamlit as st

from lingcompare.app.state import init_state, reset_state
from lingcompare.core.ingest_wordlist import parse as parse_wordlist, ValidationError
from lingcompare.core.ingest_interlinear import parse as parse_interlinear
from lingcompare.core.ingest_xlsx import parse as parse_xlsx
from lingcompare.core.ingest_docx import parse as parse_docx
from lingcompare.core.cognate_engine import run_pass_a, run_pass_b
from lingcompare.core.schema import Corpus

st.set_page_config(page_title="Load Corpora — LingCompare", layout="wide")
init_state()

st.title("Load Corpora")

st.markdown(
    "Each language can be loaded from a **wordlist CSV** (for lexical analysis), "
    "an **interlinear glossed text** (for grammar analysis), or both. "
    "When both are provided they are merged into a single corpus."
)

# ---------------------------------------------------------------------------
# Cached Pass A
# ---------------------------------------------------------------------------

@st.cache_resource
def _cached_pass_a(hash_a: str, hash_b: str, _corpus_a, _corpus_b):
    return run_pass_a(_corpus_a, _corpus_b)


def _corpus_hash(corpus) -> str:
    content = str([(w.gloss, w.ipa) for w in corpus.words])
    return hashlib.md5(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def _root_gloss(gloss: str) -> str:
    """Semantic root of a gloss label: 'eat.3SG' → 'eat', 'cat-PL' → 'cat'."""
    return gloss.lower().split(".")[0].split("-")[0].strip()


def _dedup_words(words):
    """One word per root gloss (case-insensitive).  When duplicates exist,
    keep the entry whose gloss is the shortest (typically the base form)."""
    seen: dict[str, int] = {}   # root -> index in `kept`
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
    """Combine a wordlist corpus and an interlinear corpus into one.

    Wordlist words take priority.  Interlinear words are only added when their
    root gloss is not already covered by the wordlist — this prevents inflected
    and morphologically tagged forms (cat-PL, eat.3SG, birds…) from creating
    near-duplicate candidates in Pass A.
    The merged word list is then deduped by root gloss so repeated occurrences
    of the same word within the interlinear text each appear only once.
    """
    if a is None and b is None:
        return None
    if a is None:
        return Corpus(
            language_name=language_name,
            words=_dedup_words(b.words),
            gloss_glossary=b.gloss_glossary,
        )
    if b is None:
        return Corpus(
            language_name=language_name,
            words=_dedup_words(a.words),
            gloss_glossary=a.gloss_glossary,
        )
    wordlist_roots = {_root_gloss(w.gloss) for w in a.words}
    extra = [w for w in b.words if _root_gloss(w.gloss) not in wordlist_roots]
    merged_glossary = {**a.gloss_glossary, **b.gloss_glossary}
    return Corpus(
        language_name=language_name,
        words=_dedup_words(a.words + extra),
        gloss_glossary=merged_glossary,
    )


# ---------------------------------------------------------------------------
# Corpus panel
# ---------------------------------------------------------------------------

def _corpus_panel(label: str, key_prefix: str) -> Corpus | None:
    """Render upload + paste UI for one language. Returns merged Corpus or None."""
    st.subheader(label)
    lang_name = st.text_input(
        "Language name", key=f"{key_prefix}_lang",
        placeholder="e.g. Spanish",
    )

    # ---- Wordlist (CSV / Excel / Word) ----
    with st.expander("Wordlist — CSV, Excel, or Word", expanded=True):
        st.caption(
            "Two columns: **gloss** and **IPA**. "
            "Accepted formats: CSV/TXT, Excel (.xlsx), Word (.docx). "
            "Header row optional. Example CSV: `water,aɣwa`"
        )
        wl_upload = st.file_uploader(
            "Upload wordlist", type=["csv", "txt", "xlsx", "docx"],
            key=f"{key_prefix}_wl_file",
        )
        wl_paste = st.text_area(
            "…or paste CSV here",
            key=f"{key_prefix}_wl_paste",
            height=120,
            placeholder="gloss,IPA\nwater,aɣwa\nfire,fweɣo",
        )

    # ---- Interlinear glossed text ----
    with st.expander("Interlinear glossed text", expanded=False):
        st.caption(
            "Blocks separated by blank lines. Each block needs an `IPA:` line "
            "and a `GLOSS:` line. Hyphens mark morpheme boundaries: `aɣwa-s` / `water-PL`."
        )
        il_upload = st.file_uploader(
            "Upload interlinear text", type=["txt"],
            key=f"{key_prefix}_il_file",
        )
        il_paste = st.text_area(
            "…or paste interlinear text here",
            key=f"{key_prefix}_il_paste",
            height=120,
            placeholder="IPA:   aɣwa-s\nGLOSS: water-PL\nTRANS: waters",
        )

    # ---- Parse wordlist ----
    wl_corpus: Corpus | None = None

    if wl_upload is not None:
        file_bytes = wl_upload.read()
        name = wl_upload.name.lower()
        if name.endswith(".xlsx") or name.endswith(".xlsm") or name.endswith(".ods"):
            corpus, errors = parse_xlsx(file_bytes, language_name=lang_name or "Unknown")
        elif name.endswith(".docx"):
            corpus, errors = parse_docx(file_bytes, language_name=lang_name or "Unknown")
        else:
            corpus, errors = parse_wordlist(
                file_bytes.decode("utf-8"), language_name=lang_name or "Unknown"
            )
        if errors:
            st.error(f"**{len(errors)} wordlist error(s)** — fix before proceeding:")
            for err in errors[:20]:
                st.markdown(f"- {err}")
            if len(errors) > 20:
                st.caption(f"…and {len(errors) - 20} more.")
        else:
            st.success(f"Wordlist: {len(corpus.words)} words, "
                       f"{len(corpus.phoneme_inventory)} unique phonemes.")
            wl_corpus = corpus
    elif wl_paste.strip():
        corpus, errors = parse_wordlist(wl_paste.strip(), language_name=lang_name or "Unknown")
        if errors:
            st.error(f"**{len(errors)} wordlist error(s)** — fix before proceeding:")
            for err in errors[:20]:
                st.markdown(f"- {err}")
            if len(errors) > 20:
                st.caption(f"…and {len(errors) - 20} more.")
        else:
            st.success(f"Wordlist: {len(corpus.words)} words, "
                       f"{len(corpus.phoneme_inventory)} unique phonemes.")
            wl_corpus = corpus

    # ---- Parse interlinear ----
    il_corpus: Corpus | None = None
    il_raw: str | None = None
    if il_upload is not None:
        il_raw = il_upload.read().decode("utf-8")
    elif il_paste.strip():
        il_raw = il_paste.strip()

    if il_raw is not None:
        corpus, errors = parse_interlinear(il_raw, language_name=lang_name or "Unknown")
        if errors:
            st.error(f"**{len(errors)} interlinear error(s)** — fix before proceeding:")
            for err in errors[:20]:
                st.markdown(f"- {err}")
            if len(errors) > 20:
                st.caption(f"…and {len(errors) - 20} more.")
        else:
            n_morph = sum(len(w.morphemes) for w in corpus.words)
            st.success(f"Interlinear: {len(corpus.words)} words, "
                       f"{n_morph} morphemes with gloss tags.")
            il_corpus = corpus

    return _merge_corpora(wl_corpus, il_corpus, lang_name or "Unknown")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

col_a, col_b = st.columns(2)

with col_a:
    result_a = _corpus_panel("Corpus A", "a")
    if result_a is not None:
        st.session_state.corpus_a = result_a

with col_b:
    result_b = _corpus_panel("Corpus B", "b")
    if result_b is not None:
        st.session_state.corpus_b = result_b

st.divider()

# ---------------------------------------------------------------------------
# Analysis controls
# ---------------------------------------------------------------------------

both_loaded = (
    st.session_state.corpus_a is not None
    and st.session_state.corpus_b is not None
)

col_run, col_reset = st.columns([3, 1])

with col_run:
    if both_loaded:
        if st.button("Run Analysis", type="primary", use_container_width=True):
            with st.spinner("Running phonetic alignment…"):
                ca = st.session_state.corpus_a
                cb = st.session_state.corpus_b
                candidates = _cached_pass_a(
                    _corpus_hash(ca), _corpus_hash(cb), ca, cb
                )
                corrs, candidates = run_pass_b(candidates)
                st.session_state.candidates = candidates
                st.session_state.correspondences = corrs
                st.session_state.pass_a_done = True
                st.session_state.pass_b_done = True
            n = len(candidates)
            st.success(
                f"Analysis complete — {n} candidate pair(s) found. "
                "Go to **Lexicon / Cognates** to review them."
            )
    else:
        st.info("Load both corpora above, then click **Run Analysis**.")

with col_reset:
    if st.button("Clear & Reload", use_container_width=True):
        reset_state()
        st.rerun()

# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

if st.session_state.corpus_a or st.session_state.corpus_b:
    st.divider()
    st.subheader("Loaded words preview")
    prev_a, prev_b = st.columns(2)

    import pandas as pd

    with prev_a:
        ca = st.session_state.corpus_a
        if ca:
            st.markdown(f"**{ca.language_name}**")
            df = pd.DataFrame([{"gloss": w.gloss, "IPA": w.ipa} for w in ca.words])
            st.dataframe(df, use_container_width=True, hide_index=True)

    with prev_b:
        cb = st.session_state.corpus_b
        if cb:
            st.markdown(f"**{cb.language_name}**")
            df = pd.DataFrame([{"gloss": w.gloss, "IPA": w.ipa} for w in cb.words])
            st.dataframe(df, use_container_width=True, hide_index=True)
