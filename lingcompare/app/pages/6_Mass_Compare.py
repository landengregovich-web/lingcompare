"""Mass Compare page — N-language similarity matrix and concept table."""

from __future__ import annotations
import pandas as pd
import streamlit as st

from lingcompare.app.state import init_state
from lingcompare.core.cognate_engine import run_pass_b

st.set_page_config(page_title="Mass Compare — LingCompare", layout="wide")
init_state()

st.title("Mass Compare")
st.caption(
    "Overview across all loaded languages. "
    "Run **Analyse all pairs** on the Load Corpora page first."
)

corpora = [c for c in st.session_state.corpora if c is not None]
pair_results = st.session_state.pair_results   # dict[(i,j)] -> (corrs, cands)

if len(corpora) < 2:
    st.info("Load at least two languages on the Load Corpora page.")
    st.stop()

if not pair_results:
    st.info('Click **Analyse all pairs** on the Load Corpora page to populate this view.')
    st.stop()

names = [c.language_name for c in corpora]
n = len(corpora)

# ---------------------------------------------------------------------------
# 1. Language similarity matrix
# ---------------------------------------------------------------------------

st.subheader("Language similarity matrix")
st.caption(
    "Each cell shows how phonetically similar the two languages are, "
    "averaged across all candidate pairs (100 = identical, 0 = maximally different). "
    "Only cells where analysis has been run are filled."
)

sim_data: dict[str, dict[str, str]] = {name: {} for name in names}
for i in range(n):
    for j in range(n):
        if i == j:
            sim_data[names[i]][names[j]] = "—"
        else:
            key = (min(i, j), max(i, j))
            if key in pair_results:
                _, cands = pair_results[key]
                if cands:
                    avg_dist = sum(c.phonetic_score for c in cands) / len(cands)
                    pct = round((1 - avg_dist) * 100, 1)
                    sim_data[names[i]][names[j]] = f"{pct}%"
                else:
                    sim_data[names[i]][names[j]] = "n/a"
            else:
                sim_data[names[i]][names[j]] = ""

sim_df = pd.DataFrame(sim_data).T
sim_df = sim_df[names]  # consistent column order

# Colour numeric cells green→red
def _colour(val):
    if not isinstance(val, str) or val in ("—", "n/a", ""):
        return ""
    try:
        pct = float(val.rstrip("%"))
    except ValueError:
        return ""
    g = int(pct * 2.55)
    r = 255 - g
    return f"background-color: rgb({r},{g},80); color: black"

_styler = sim_df.style.map if hasattr(sim_df.style, "map") else sim_df.style.applymap
styled = _styler(_colour)
st.dataframe(styled, use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Set active pair for detail pages
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Select pair for detailed analysis")
st.caption("Choose two languages to view in the Phonology, Lexicon, and Grammar pages.")

col1, col2, col3 = st.columns([3, 3, 2])
with col1:
    sel_a = st.selectbox("Language A", options=range(n),
                         format_func=lambda i: names[i], key="mc_sel_a")
with col2:
    opts_b = [i for i in range(n) if i != sel_a]
    sel_b = st.selectbox("Language B", options=opts_b,
                         format_func=lambda i: names[i], key="mc_sel_b")
with col3:
    st.write("")
    if st.button("Set as active pair", type="primary", use_container_width=True):
        key = (min(sel_a, sel_b), max(sel_a, sel_b))
        if key in pair_results:
            corrs, cands = pair_results[key]
            st.session_state.corpus_a = corpora[sel_a]
            st.session_state.corpus_b = corpora[sel_b]
            st.session_state.candidates = list(cands)
            st.session_state.correspondences = list(corrs)
            st.session_state.pass_a_done = True
            st.session_state.pass_b_done = True
            st.success(f"Active pair set to **{names[sel_a]}** vs **{names[sel_b]}**.")
        else:
            st.warning("That pair hasn't been analysed yet. Run **Analyse all pairs** first.")

# ---------------------------------------------------------------------------
# 3. Concept table
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Concept table")
st.caption(
    "Each row is a concept (gloss). Columns show the IPA form in each language. "
    "Concepts present in only one language are hidden. "
    "Use the filter to focus on concepts shared across many languages."
)

# Collect all glosses per language
gloss_to_ipa: list[dict[str, str]] = []  # index = corpus index
for corpus in corpora:
    gloss_to_ipa.append({w.gloss.lower(): w.ipa for w in corpus.words})

# Count how many languages have each gloss
all_glosses: dict[str, list[str]] = {}   # gloss -> list of display glosses (preserves case)
for gi, g2i in enumerate(gloss_to_ipa):
    for g in g2i:
        if g not in all_glosses:
            all_glosses[g] = [w.gloss for w in corpora[gi].words if w.gloss.lower() == g]
        # else already recorded

# Filter: glosses present in at least `min_langs` languages
min_langs = st.slider(
    "Show concepts present in at least … languages",
    min_value=2, max_value=max(2, n), value=2, step=1,
)

rows = []
for g_lower, display_list in sorted(all_glosses.items()):
    count = sum(1 for g2i in gloss_to_ipa if g_lower in g2i)
    if count < min_langs:
        continue
    display_gloss = display_list[0] if display_list else g_lower
    row: dict[str, str] = {"Concept": display_gloss}
    for lang_idx, (lang_name, g2i) in enumerate(zip(names, gloss_to_ipa)):
        row[lang_name] = g2i.get(g_lower, "")
    # Similarity hint: average phonetic score across all pairs for this concept
    scores = []
    for i in range(n):
        for j in range(i + 1, n):
            key = (i, j)
            if key not in pair_results:
                continue
            _, cands = pair_results[key]
            for c in cands:
                if c.word_a.gloss.lower() == g_lower or c.word_b.gloss.lower() == g_lower:
                    scores.append(c.phonetic_score)
                    break
    row["Avg similarity"] = f"{round((1 - sum(scores)/len(scores)) * 100)}%" if scores else ""
    rows.append(row)

if rows:
    concept_df = pd.DataFrame(rows)
    # Highlight empty cells (language missing that concept)
    def _hl_empty(val):
        return "color: #aaa" if val == "" else ""
    st.dataframe(
        (concept_df.style.map if hasattr(concept_df.style, "map") else concept_df.style.applymap)(_hl_empty, subset=names),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(rows)} concept(s) shown.")
else:
    st.info("No concepts shared across the selected number of languages.")
