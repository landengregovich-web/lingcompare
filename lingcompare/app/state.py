"""Shared session_state schema for the LingCompare Streamlit app.

Import and call init_state() at the top of every page to guarantee all
keys exist before any page logic reads them.
"""

from __future__ import annotations
import streamlit as st


INITIAL_STATE: dict = {
    # Single-pair (legacy, used by Phonology / Lexicon / Grammar pages)
    "corpus_a": None,          # Corpus | None
    "corpus_b": None,          # Corpus | None
    "candidates": [],          # list[CandidatePair]
    "correspondences": [],     # list[SoundCorrespondence]
    "pass_a_done": False,
    "pass_b_done": False,
    "gloss_tag_mappings": [],

    # Multi-language
    "corpora": [],             # list[Corpus]  — all loaded languages
    "pair_results": {},        # dict[(int,int), (correspondences, candidates)]
    "lang_count": 2,           # number of language panels shown in Load Corpora
}


def init_state() -> None:
    """Initialise missing session_state keys with their defaults."""
    for key, default in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_state() -> None:
    """Clear all analysis state (keeps nothing — forces full reload)."""
    for key in INITIAL_STATE:
        st.session_state[key] = (
            [] if isinstance(INITIAL_STATE[key], list) else INITIAL_STATE[key]
        )
