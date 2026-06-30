"""LingCompare — home page and app entry point."""

import streamlit as st
from lingcompare.app.state import init_state

st.set_page_config(
    page_title="LingCompare",
    page_icon="🔤",
    layout="wide",
)

init_state()

st.title("LingCompare")
st.markdown(
    """
A tool for comparing two linguistic corpora across phonology, lexicon, and grammar.
It proposes candidate correspondences and shows the evidence behind each score.
**The tool does not assert truth** — it surfaces candidates for you to accept or reject.

### How to use
1. **Load Corpora** — upload or paste wordlists for Language A and Language B.
2. **Phonology** — inspect side-by-side phoneme inventories.
3. **Lexicon / Cognates** — browse proposed word correspondences, accept or reject them.
4. **Grammar** — review proposed grammatical tag correspondences.
5. **Report** — export all results.

Use the sidebar to navigate between pages.
"""
)

# Status summary
col1, col2, col3 = st.columns(3)
with col1:
    if st.session_state.corpus_a:
        st.success(f"Corpus A: **{st.session_state.corpus_a.language_name}** "
                   f"({len(st.session_state.corpus_a.words)} words)")
    else:
        st.info("Corpus A: not loaded")

with col2:
    if st.session_state.corpus_b:
        st.success(f"Corpus B: **{st.session_state.corpus_b.language_name}** "
                   f"({len(st.session_state.corpus_b.words)} words)")
    else:
        st.info("Corpus B: not loaded")

with col3:
    n = len(st.session_state.candidates)
    if n:
        n_acc = sum(1 for c in st.session_state.candidates if c.status == "accepted")
        n_rej = sum(1 for c in st.session_state.candidates if c.status == "rejected")
        st.success(f"{n} candidates — {n_acc} accepted, {n_rej} rejected")
    else:
        st.info("No analysis run yet")


def main() -> None:
    """Console-script entry point: launches Streamlit."""
    import subprocess, sys, pathlib
    home = pathlib.Path(__file__)
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(home)], check=True)
