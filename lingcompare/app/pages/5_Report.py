"""Report page — summary statistics and export downloads.

Shows:
  - Overview metrics (accepted / rejected / pending)
  - Systematic correspondences that were confirmed
  - Accepted candidate pairs preview
  - Download buttons: candidates CSV, correspondences CSV, full JSON
"""

from __future__ import annotations
import pandas as pd
import streamlit as st

from lingcompare.app.state import init_state
from lingcompare.core.cognate_engine import run_pass_b
from lingcompare.core.export import candidates_csv, correspondences_csv, full_json
from lingcompare.core.phon_align import format_alignment
from lingcompare.core.scoring import compute_scored_evidence, score_all

st.set_page_config(page_title="Report — LingCompare", layout="wide")
init_state()

st.title("Report")

# ---------------------------------------------------------------------------
# Guard — need both corpora + candidates
# ---------------------------------------------------------------------------

if not st.session_state.corpus_a or not st.session_state.corpus_b:
    st.info("Load both corpora first (see **Load Corpora** page).")
    st.stop()

if not st.session_state.candidates:
    st.info("Run the analysis on the **Load Corpora** page first.")
    st.stop()

ca = st.session_state.corpus_a
cb = st.session_state.corpus_b
candidates = st.session_state.candidates
correspondences = st.session_state.correspondences

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

n_total = len(candidates)
n_accepted = sum(1 for c in candidates if c.status == "accepted")
n_rejected = sum(1 for c in candidates if c.status == "rejected")
n_pending = n_total - n_accepted - n_rejected

st.subheader("Overview")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total candidates", n_total)
m2.metric("Accepted", n_accepted)
m3.metric("Rejected", n_rejected)
m4.metric("Pending review", n_pending)

if n_accepted + n_rejected > 0:
    accept_rate = n_accepted / (n_accepted + n_rejected) * 100
    st.caption(
        f"{accept_rate:.0f}% of reviewed pairs accepted · "
        f"{n_accepted + n_rejected} of {n_total} reviewed"
    )

st.divider()

# ---------------------------------------------------------------------------
# Top systematic correspondences
# ---------------------------------------------------------------------------

st.subheader("Systematic sound correspondences")
if not correspondences:
    st.info("No systematic patterns detected yet. Review candidates on the Lexicon page first.")
else:
    positive = [c for c in correspondences if c.weight > 0]
    positive.sort(key=lambda c: -c.weight)
    if positive:
        rows = [
            {
                ca.language_name: c.symbol_a,
                cb.language_name: c.symbol_b,
                "Position": c.position,
                "Weight": f"{c.weight:.3f}",
                "Support pairs": len(c.supporting_pairs),
            }
            for c in positive
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No positive correspondences detected.")

st.divider()

# ---------------------------------------------------------------------------
# Accepted pairs preview
# ---------------------------------------------------------------------------

st.subheader("Accepted pairs")
accepted = [c for c in candidates if c.status == "accepted"]
if not accepted:
    st.info(
        "No pairs accepted yet. Use the **Lexicon / Cognates** page "
        "to review and accept candidate pairs."
    )
else:
    rows = []
    for pair in sorted(accepted, key=lambda p: -p.final_score):
        align_lines = format_alignment(pair.alignment).split("\n")
        rows.append({
            f"{ca.language_name} gloss": pair.word_a.gloss,
            f"{ca.language_name} IPA": f"/{pair.word_a.ipa}/",
            f"{cb.language_name} IPA": f"/{pair.word_b.ipa}/",
            "Alignment A": align_lines[0],
            "Alignment B": align_lines[1],
            "Phonetic dist.": f"{pair.phonetic_score:.3f}",
            "Confidence": f"{pair.final_score:.1%}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.subheader("Export")
st.caption(
    "All exports reflect the current state — accept/reject decisions are included. "
    "Re-download after further review to capture changes."
)

# Compute full scored evidence for the export
@st.cache_data(show_spinner="Computing evidence scores…")
def _build_scored(cand_key: str):
    return score_all(candidates, correspondences, cb.phoneme_inventory)

try:
    scored = _build_scored(str(id(candidates)))
except Exception:
    scored = None

# Grab tag mappings from session state if present
tag_mappings = st.session_state.get("gloss_tag_mappings", None)

dl1, dl2, dl3 = st.columns(3)

with dl1:
    csv_data = candidates_csv(
        candidates,
        lang_a=ca.language_name,
        lang_b=cb.language_name,
        scored=scored,
    )
    st.download_button(
        label="Download candidates CSV",
        data=csv_data.encode("utf-8"),
        file_name="lingcompare_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(f"{len(candidates)} rows · includes alignment + all evidence factors")

with dl2:
    corr_data = correspondences_csv(correspondences)
    st.download_button(
        label="Download correspondences CSV",
        data=corr_data.encode("utf-8"),
        file_name="lingcompare_correspondences.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(f"{len(correspondences)} rows · weight = sum of accept/reject signals")

with dl3:
    json_data = full_json(
        ca, cb, candidates, correspondences,
        tag_mappings=tag_mappings,
        scored=scored,
    )
    st.download_button(
        label="Download full JSON",
        data=json_data.encode("utf-8"),
        file_name="lingcompare_full.json",
        mime="application/json",
        use_container_width=True,
    )
    st.caption("Complete structured dump — candidates, correspondences, inventories, tags")

st.divider()

# ---------------------------------------------------------------------------
# Session info
# ---------------------------------------------------------------------------

st.subheader("Session info")
info_rows = [
    {"Field": "Language A", "Value": ca.language_name},
    {"Field": "Language B", "Value": cb.language_name},
    {"Field": "Words in A", "Value": len(ca.words)},
    {"Field": "Words in B", "Value": len(cb.words)},
    {"Field": "Phonemes in A", "Value": len(ca.phoneme_inventory)},
    {"Field": "Phonemes in B", "Value": len(cb.phoneme_inventory)},
    {"Field": "Candidate pairs", "Value": n_total},
    {"Field": "Systematic correspondences", "Value": len(correspondences)},
]
st.dataframe(pd.DataFrame(info_rows), use_container_width=True, hide_index=True)
