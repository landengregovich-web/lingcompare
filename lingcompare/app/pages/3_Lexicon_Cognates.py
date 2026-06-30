"""Lexicon / Cognates page — the primary interactive page.

Displays proposed word-level correspondences sorted by confidence score.
Each row is expandable to show the phonetic alignment and full evidence.
Accept / Reject buttons feed back into Pass B systematicity scoring.
"""

from __future__ import annotations
import streamlit as st

from lingcompare.app.state import init_state
from lingcompare.core.cognate_engine import run_pass_b, CandidatePair
from lingcompare.core.phon_align import format_alignment
from lingcompare.core.scoring import compute_scored_evidence, sound_change_plausibility, WEIGHTS

st.set_page_config(page_title="Lexicon / Cognates — LingCompare", layout="wide")
init_state()

st.title("Lexicon / Cognates")

# ---------------------------------------------------------------------------
# Guard: need analysis results
# ---------------------------------------------------------------------------

if not st.session_state.pass_a_done:
    st.info("No analysis results yet. Go to **Load Corpora** and click **Run Analysis**.")
    st.stop()

candidates: list[CandidatePair] = st.session_state.candidates
correspondences = st.session_state.correspondences

if not candidates:
    st.warning("No candidate pairs found. Check that your corpora share gloss labels.")
    st.stop()

# ---------------------------------------------------------------------------
# Sorting and filtering controls
# ---------------------------------------------------------------------------

col_sort, col_filter, col_stats = st.columns([2, 2, 2])

with col_sort:
    sort_by = st.selectbox(
        "Sort by",
        ["Confidence (high→low)", "Confidence (low→high)", "Gloss (A→Z)"],
        index=0,
    )

with col_filter:
    show_filter = st.multiselect(
        "Show status",
        ["pending", "accepted", "rejected"],
        default=["pending", "accepted", "rejected"],
    )

with col_stats:
    n_total = len(candidates)
    n_acc = sum(1 for c in candidates if c.status == "accepted")
    n_rej = sum(1 for c in candidates if c.status == "rejected")
    n_pend = n_total - n_acc - n_rej
    st.metric("Total", n_total)

st.caption(f"**{n_pend}** pending · **{n_acc}** accepted · **{n_rej}** rejected")

# Apply filter and sort
visible = [c for c in candidates if c.status in show_filter]

if sort_by == "Confidence (high→low)":
    visible.sort(key=lambda c: c.final_score, reverse=True)
elif sort_by == "Confidence (low→high)":
    visible.sort(key=lambda c: c.final_score)
else:
    visible.sort(key=lambda c: c.word_a.gloss)

st.divider()

# ---------------------------------------------------------------------------
# Candidate rows
# ---------------------------------------------------------------------------

# Map gloss to index in the master candidates list for stable button keys.
# Index by position in candidates list (not by gloss) since there can be
# multiple candidates per gloss.
idx_map = {id(c): i for i, c in enumerate(candidates)}


def _status_badge(status: str) -> str:
    return {"pending": "⬜", "accepted": "✅", "rejected": "❌"}.get(status, "")


def _score_bar(score: float) -> str:
    """Simple ASCII progress bar for the confidence score."""
    filled = int(score * 10)
    return "█" * filled + "░" * (10 - filled)


for pair in visible:
    master_idx = idx_map[id(pair)]
    ca = st.session_state.corpus_a
    cb = st.session_state.corpus_b
    lang_a = ca.language_name if ca else "A"
    lang_b = cb.language_name if cb else "B"

    badge = _status_badge(pair.status)
    score_pct = int(pair.final_score * 100)
    header = (
        f"{badge} **{pair.word_a.gloss}** — "
        f"/{pair.word_a.ipa}/ ({lang_a}) ↔ "
        f"/{pair.word_b.ipa}/ ({lang_b}) "
        f"· confidence: {score_pct}%"
    )

    with st.expander(header, expanded=False):
        ev_col, ctrl_col = st.columns([4, 1])

        with ev_col:
            # Alignment display
            st.markdown("**Phonetic alignment**")
            align_lines = format_alignment(pair.alignment).split("\n")
            st.code(f"{lang_a}: {align_lines[0]}\n{lang_b}: {align_lines[1]}")

            # Per-column sound change plausibility
            col_rows = []
            for pa, pb in zip(pair.alignment.aligned_a, pair.alignment.aligned_b):
                sym_a = pa.ipa_symbol if pa else "∅"
                sym_b = pb.ipa_symbol if pb else "∅"
                plab = sound_change_plausibility(
                    pa.ipa_symbol if pa else None,
                    pb.ipa_symbol if pb else None,
                )
                col_rows.append({lang_a: sym_a, lang_b: sym_b,
                                  "plausibility": f"{plab:.0%}"})
            import pandas as pd
            st.dataframe(pd.DataFrame(col_rows), use_container_width=True,
                         hide_index=True)

            # Full scored evidence breakdown
            inv_b = cb.phoneme_inventory if cb else set()
            evidence = compute_scored_evidence(pair, correspondences, inv_b)
            st.markdown("**Evidence breakdown**")
            st.markdown(f"_{evidence.narrative}_")
            factor_rows = [
                {"Factor": k, "Score": f"{v:.0%}",
                 "Weight": f"{WEIGHTS[k]:.0%}",
                 "Contribution": f"{v * WEIGHTS[k]:.0%}"}
                for k, v in evidence.factor_scores.items()
            ]
            st.dataframe(pd.DataFrame(factor_rows), use_container_width=True,
                         hide_index=True)

            # Which systematic correspondences support this pair?
            supporting_corrs = [
                c for c in correspondences
                if pair in c.supporting_pairs and c.weight > 0
            ]
            if supporting_corrs:
                st.markdown("**Supporting systematic patterns**")
                for corr in sorted(supporting_corrs, key=lambda c: -c.weight):
                    sym_a = corr.symbol_a or "∅"
                    sym_b = corr.symbol_b or "∅"
                    n_sup = len(corr.supporting_pairs)
                    st.markdown(
                        f"- `{sym_a} → {sym_b}` ({corr.position}, "
                        f"{n_sup} pair{'s' if n_sup != 1 else ''}, "
                        f"weight {corr.weight:+.2f})"
                    )

        with ctrl_col:
            st.markdown("&nbsp;")  # vertical spacing

            accept_key = f"accept_{master_idx}"
            reject_key = f"reject_{master_idx}"
            undo_key = f"undo_{master_idx}"

            if pair.status == "pending":
                if st.button("✅ Accept", key=accept_key, use_container_width=True):
                    candidates[master_idx].status = "accepted"
                    corrs, updated = run_pass_b(candidates)
                    st.session_state.correspondences = corrs
                    st.session_state.candidates = updated
                    st.rerun()
                if st.button("❌ Reject", key=reject_key, use_container_width=True):
                    candidates[master_idx].status = "rejected"
                    corrs, updated = run_pass_b(candidates)
                    st.session_state.correspondences = corrs
                    st.session_state.candidates = updated
                    st.rerun()

            else:
                st.markdown(
                    f"**{'Accepted' if pair.status == 'accepted' else 'Rejected'}**"
                )
                if st.button("↩ Undo", key=undo_key, use_container_width=True):
                    candidates[master_idx].status = "pending"
                    corrs, updated = run_pass_b(candidates)
                    st.session_state.correspondences = corrs
                    st.session_state.candidates = updated
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Systematic correspondences panel
# ---------------------------------------------------------------------------

st.subheader("Systematic sound correspondences")
st.caption(
    "Patterns appearing in 2 or more candidate pairs. "
    "Accepting / rejecting pairs above updates these live."
)

if not correspondences:
    st.info("No systematic patterns detected yet (need 2+ candidate pairs with the same column correspondence).")
else:
    ca = st.session_state.corpus_a
    cb = st.session_state.corpus_b
    lang_a = ca.language_name if ca else "A"
    lang_b = cb.language_name if cb else "B"

    import pandas as pd
    rows = []
    for corr in sorted(correspondences, key=lambda c: (-len(c.supporting_pairs), -c.weight)):
        sym_a = corr.symbol_a or "∅ (gap)"
        sym_b = corr.symbol_b or "∅ (gap)"
        n_sup = len(corr.supporting_pairs)
        n_acc = sum(1 for p in corr.supporting_pairs if p.status == "accepted")
        n_rej = sum(1 for p in corr.supporting_pairs if p.status == "rejected")
        rows.append({
            lang_a: sym_a,
            lang_b: sym_b,
            "Position": corr.position,
            "# pairs": n_sup,
            "Accepted": n_acc,
            "Rejected": n_rej,
            "Weight": f"{corr.weight:+.2f}",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
