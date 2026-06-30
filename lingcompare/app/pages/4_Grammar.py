"""Grammar page — gloss-tag correspondences, morpheme alignment, typology.

Three panels:
1. Proposed gloss-tag correspondences with confirm/reject controls.
2. Morpheme-level alignment for confirmed tag pairs (reuses cognate engine).
3. Morphological typology comparison table.
"""

from __future__ import annotations
import pandas as pd
import streamlit as st

from lingcompare.app.state import init_state
from lingcompare.core.gloss_match import propose_tag_correspondences, morphemes_for_tag, GlossTagMapping
from lingcompare.core.morph_typology import compare_typology
from lingcompare.core.schema import Word
from lingcompare.core.phon_align import align_pair, format_alignment

st.set_page_config(page_title="Grammar — LingCompare", layout="wide")
init_state()

st.title("Grammar")

if not st.session_state.corpus_a or not st.session_state.corpus_b:
    st.info("Load both corpora first (see **Load Corpora** page).")
    st.stop()

ca = st.session_state.corpus_a
cb = st.session_state.corpus_b

# ---------------------------------------------------------------------------
# Collect / initialise gloss-tag mappings in session state
# ---------------------------------------------------------------------------

if "gloss_tag_mappings" not in st.session_state:
    st.session_state.gloss_tag_mappings = []

# (Re-)propose whenever corpora change, or if mappings list is empty
if not st.session_state.gloss_tag_mappings:
    proposed = propose_tag_correspondences(ca, cb)
    st.session_state.gloss_tag_mappings = proposed

mappings: list[GlossTagMapping] = st.session_state.gloss_tag_mappings

# ---------------------------------------------------------------------------
# Panel 1 — Proposed gloss-tag correspondences
# ---------------------------------------------------------------------------

st.subheader("Proposed gloss-tag correspondences")
st.caption(
    "Tags are user-defined per corpus and never assumed to match across corpora. "
    "These are candidates based on fuzzy string matching — confirm, reject, or edit them."
)

if not mappings:
    st.info(
        "No gloss tags found. Tags are extracted from morpheme breakdowns in interlinear text. "
        "Upload interlinear data on the **Load Corpora** page, or add morpheme breakdown "
        "columns to your wordlists."
    )
else:
    n_confirmed = sum(1 for m in mappings if m.status == "confirmed")
    n_rejected = sum(1 for m in mappings if m.status == "rejected")
    st.caption(f"{len(mappings)} proposals · {n_confirmed} confirmed · {n_rejected} rejected")

    for i, mapping in enumerate(mappings):
        badge = {"proposed": "⬜", "confirmed": "✅", "rejected": "❌"}.get(mapping.status, "")
        score_pct = int(mapping.combined_score)
        header = (
            f"{badge} `{mapping.tag_a}` ({ca.language_name}) ↔ "
            f"`{mapping.tag_b}` ({cb.language_name}) · {score_pct}% match"
        )

        with st.expander(header, expanded=(mapping.status == "proposed" and i < 5)):
            ev_col, ctrl_col = st.columns([4, 1])

            with ev_col:
                st.markdown("**Evidence**")
                st.markdown(f"- Tag string similarity: {mapping.tag_similarity:.0f}/100")
                if mapping.def_similarity > 0:
                    st.markdown(f"- Definition similarity: {mapping.def_similarity:.0f}/100")
                    st.markdown(f"- Combined score: {mapping.combined_score:.0f}/100")

                def_a = ca.gloss_glossary.get(mapping.tag_a, "_(no definition)_")
                def_b = cb.gloss_glossary.get(mapping.tag_b, "_(no definition)_")
                st.markdown(f"- `{mapping.tag_a}` defined as: {def_a}")
                st.markdown(f"- `{mapping.tag_b}` defined as: {def_b}")

                # Morpheme occurrence counts
                morph_a = morphemes_for_tag(ca, mapping.tag_a)
                morph_b = morphemes_for_tag(cb, mapping.tag_b)
                st.markdown(
                    f"- Occurrences: {len(morph_a)} in {ca.language_name}, "
                    f"{len(morph_b)} in {cb.language_name}"
                )

            with ctrl_col:
                st.markdown("&nbsp;")
                if mapping.status == "proposed":
                    if st.button("✅ Confirm", key=f"confirm_tag_{i}", use_container_width=True):
                        st.session_state.gloss_tag_mappings[i].status = "confirmed"
                        st.rerun()
                    if st.button("❌ Reject", key=f"reject_tag_{i}", use_container_width=True):
                        st.session_state.gloss_tag_mappings[i].status = "rejected"
                        st.rerun()
                else:
                    st.markdown(f"**{'Confirmed' if mapping.status == 'confirmed' else 'Rejected'}**")
                    if st.button("↩ Undo", key=f"undo_tag_{i}", use_container_width=True):
                        st.session_state.gloss_tag_mappings[i].status = "proposed"
                        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Panel 2 — Morpheme-level alignment for confirmed pairs
# ---------------------------------------------------------------------------

st.subheader("Morpheme alignment")
st.caption("Confirmed tag pairs aligned using the same phonetic engine as the Lexicon page.")

confirmed = [m for m in mappings if m.status == "confirmed"]

if not confirmed:
    st.info("Confirm tag correspondences above to see morpheme alignments.")
else:
    for mapping in confirmed:
        morphs_a = morphemes_for_tag(ca, mapping.tag_a)
        morphs_b = morphemes_for_tag(cb, mapping.tag_b)

        if not morphs_a or not morphs_b:
            st.markdown(f"**`{mapping.label()}`** — not attested in one or both corpora.")
            continue

        st.markdown(f"**`{mapping.label()}`**")
        rows = []
        for ma in morphs_a:
            if not ma.segments:
                continue
            for mb in morphs_b:
                if not mb.segments:
                    continue
                result = align_pair(ma.segments, mb.segments)
                align_lines = format_alignment(result).split("\n")
                rows.append({
                    f"{ca.language_name} morpheme": f"/{ma.ipa}/",
                    f"{cb.language_name} morpheme": f"/{mb.ipa}/",
                    "Alignment A": align_lines[0],
                    "Alignment B": align_lines[1],
                    "Distance": f"{result.normalized_score:.3f}",
                })

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No morpheme segments to align.")

st.divider()

# ---------------------------------------------------------------------------
# Panel 3 — Morphological typology comparison
# ---------------------------------------------------------------------------

st.subheader("Morphological typology")
st.caption(
    "Compares how grammatical categories are realised (prefix / suffix / infix / root) "
    "across the two corpora. Typological mismatches are flagged as relevant context for "
    "any proposed morpheme cognacy."
)

active_mappings = [m for m in mappings if m.status != "rejected"]

if not active_mappings:
    st.info("No active tag mappings to compare.")
else:
    typo_rows = compare_typology(ca, cb, active_mappings)

    if not typo_rows:
        st.info("No typology data — morpheme breakdowns needed in at least one corpus.")
    else:
        display = []
        for row in typo_rows:
            display.append({
                f"{ca.language_name} tag": row.tag_a,
                f"{cb.language_name} tag": row.tag_b,
                f"{ca.language_name} position": row.profile_a.summary(),
                f"{cb.language_name} position": row.profile_b.summary(),
                "Note": row.note(),
            })
        df = pd.DataFrame(display)
        st.dataframe(df, use_container_width=True, hide_index=True)
