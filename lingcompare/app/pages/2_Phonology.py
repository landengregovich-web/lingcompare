"""Phonology page — side-by-side phoneme inventory comparison.

Read-only: no user interaction beyond browsing. Highlights shared phonemes,
phonemes unique to A, and phonemes unique to B.
"""

from __future__ import annotations
import pandas as pd
import streamlit as st

from lingcompare.app.state import init_state
from lingcompare.core.phon_inventory import (
    extract_inventory,
    compare_inventories,
    inventory_to_rows,
    natural_class,
)

st.set_page_config(page_title="Phonology — LingCompare", layout="wide")
init_state()

st.title("Phonology")

if not st.session_state.corpus_a or not st.session_state.corpus_b:
    st.info("Load both corpora first (see **Load Corpora** page).")
    st.stop()

ca = st.session_state.corpus_a
cb = st.session_state.corpus_b

inv_a = extract_inventory(ca)
inv_b = extract_inventory(cb)
comparison = compare_inventories(inv_a, inv_b)

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"{ca.language_name} phonemes", len(inv_a))
col2.metric(f"{cb.language_name} phonemes", len(inv_b))
col3.metric("Shared", len(comparison.shared))
col4.metric("Divergent", len(comparison.only_in_a) + len(comparison.only_in_b))

st.divider()

# ---------------------------------------------------------------------------
# Side-by-side inventory tables with colour coding
# ---------------------------------------------------------------------------

shared_syms = {p.ipa_symbol for p in comparison.shared}
only_a_syms = {p.ipa_symbol for p in comparison.only_in_a}
only_b_syms = {p.ipa_symbol for p in comparison.only_in_b}


def style_inventory(df: pd.DataFrame, unique_syms: set[str], other_unique_syms: set[str]):
    """Colour rows: shared = default, unique to this lang = green, absent here but in other = n/a."""
    def row_style(row):
        sym = row["IPA"]
        if sym in unique_syms:
            return ["background-color: #d4edda; color: #155724"] * len(row)
        return [""] * len(row)
    return df.style.apply(row_style, axis=1)


col_a, col_b = st.columns(2)

with col_a:
    st.subheader(f"{ca.language_name} — {len(inv_a)} phonemes")
    st.caption("Green = unique to this language")
    rows_a = inventory_to_rows(inv_a)
    df_a = pd.DataFrame(rows_a)
    styled_a = style_inventory(df_a, only_a_syms, only_b_syms)
    st.dataframe(styled_a, use_container_width=True, hide_index=True)

with col_b:
    st.subheader(f"{cb.language_name} — {len(inv_b)} phonemes")
    st.caption("Green = unique to this language")
    rows_b = inventory_to_rows(inv_b)
    df_b = pd.DataFrame(rows_b)
    styled_b = style_inventory(df_b, only_b_syms, only_a_syms)
    st.dataframe(styled_b, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Overlap and gap summary
# ---------------------------------------------------------------------------

st.subheader("Inventory overlap and gaps")

shared_sorted = sorted(shared_syms)
only_a_sorted = sorted(only_a_syms)
only_b_sorted = sorted(only_b_syms)

col_s, col_ua, col_ub = st.columns(3)

with col_s:
    st.markdown(f"**Shared ({len(shared_sorted)})**")
    if shared_sorted:
        # Group by natural class for readability
        by_class: dict[str, list[str]] = {}
        for sym in shared_sorted:
            cls = natural_class(inv_a[sym])
            by_class.setdefault(cls, []).append(sym)
        for cls, syms in sorted(by_class.items()):
            st.markdown(f"*{cls}:* {' '.join(syms)}")
    else:
        st.markdown("_(none)_")

with col_ua:
    st.markdown(f"**Only in {ca.language_name} ({len(only_a_sorted)})**")
    if only_a_sorted:
        by_class = {}
        for sym in only_a_sorted:
            cls = natural_class(inv_a[sym])
            by_class.setdefault(cls, []).append(sym)
        for cls, syms in sorted(by_class.items()):
            st.markdown(f"*{cls}:* {' '.join(syms)}")
    else:
        st.markdown("_(none)_")

with col_ub:
    st.markdown(f"**Only in {cb.language_name} ({len(only_b_sorted)})**")
    if only_b_sorted:
        by_class = {}
        for sym in only_b_sorted:
            cls = natural_class(inv_b[sym])
            by_class.setdefault(cls, []).append(sym)
        for cls, syms in sorted(by_class.items()):
            st.markdown(f"*{cls}:* {' '.join(syms)}")
    else:
        st.markdown("_(none)_")
