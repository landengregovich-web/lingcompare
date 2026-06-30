"""Tests for core/phon_align.py.

Key sanity check: fuego/fogo (known cognates, minimal distance) must score
better (lower normalized_score) than fuego/agua (semantically unrelated pair).
"""

import pytest
from lingcompare.core.schema import Phoneme
from lingcompare.core.phon_align import (
    align_pair,
    phoneme_distance,
    format_alignment,
    AlignmentResult,
    GAP_PENALTY,
)
from lingcompare.core.ingest_wordlist import parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def word_segments(corpus, gloss: str) -> list[Phoneme]:
    for w in corpus.words:
        if w.gloss == gloss:
            return w.segments
    raise KeyError(f"No word with gloss {gloss!r}")


# ---------------------------------------------------------------------------
# phoneme_distance tests
# ---------------------------------------------------------------------------

def test_identical_phonemes_distance_zero():
    p1 = Phoneme.from_ipa("p")
    p2 = Phoneme.from_ipa("p")
    assert phoneme_distance(p1, p2) == 0.0


def test_similar_phonemes_low_distance():
    p = Phoneme.from_ipa("p")
    b = Phoneme.from_ipa("b")
    dist = phoneme_distance(p, b)
    assert 0.0 < dist < 0.3, f"p/b distance should be small, got {dist}"


def test_dissimilar_phonemes_high_distance():
    p = Phoneme.from_ipa("p")
    n = Phoneme.from_ipa("n")
    dist_pn = phoneme_distance(p, n)
    p2 = Phoneme.from_ipa("p")
    b = Phoneme.from_ipa("b")
    dist_pb = phoneme_distance(p2, b)
    assert dist_pn > dist_pb, f"p/n ({dist_pn:.3f}) should be farther than p/b ({dist_pb:.3f})"


def test_vowel_consonant_high_distance():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    dist = phoneme_distance(p, a)
    assert dist > 0.3, f"p/a distance should be large, got {dist}"


# ---------------------------------------------------------------------------
# align_pair structural tests
# ---------------------------------------------------------------------------

def test_identical_sequences_zero_distance():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    seq = [p, a]
    result = align_pair(seq, seq)
    assert result.raw_distance == 0.0
    assert result.normalized_score == 0.0
    assert len(result.aligned_a) == 2
    assert len(result.aligned_b) == 2


def test_single_phoneme_identical():
    p = Phoneme.from_ipa("p")
    result = align_pair([p], [p])
    assert result.raw_distance == 0.0


def test_empty_sequences():
    result = align_pair([], [])
    assert result.raw_distance == 0.0
    assert result.normalized_score == 0.0


def test_one_empty_sequence_all_gaps():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    result = align_pair([p, a], [])
    assert result.raw_distance == pytest.approx(2 * GAP_PENALTY)
    assert all(col == GAP_PENALTY for col in result.column_scores)
    assert all(b is None for b in result.aligned_b)


def test_alignment_lengths_equal():
    """aligned_a and aligned_b must be the same length (column-aligned)."""
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    b = Phoneme.from_ipa("b")
    result = align_pair([p, a, p], [b, a])
    assert len(result.aligned_a) == len(result.aligned_b) == len(result.column_scores)


def test_normalized_score_bounded():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    n = Phoneme.from_ipa("n")
    result = align_pair([p, a], [n, n])
    assert 0.0 <= result.normalized_score <= 1.0


# ---------------------------------------------------------------------------
# Sanity check: real Spanish/Portuguese cognates
# ---------------------------------------------------------------------------

ES_CSV = (
    "gloss,IPA_form\n"
    "fire,fweɣo\n"
    "water,aɣwa\n"
    "son,ixo\n"
)

PT_CSV = (
    "gloss,IPA_form\n"
    "fire,foɡu\n"
    "water,aɡwa\n"
    "son,fiʎu\n"
)


def test_cognate_pair_scores_better_than_unrelated():
    """fuego/fogo (cognates, both mean 'fire') must align closer than fuego/agua."""
    es, _ = parse(ES_CSV, language_name="Spanish")
    pt, _ = parse(PT_CSV, language_name="Portuguese")

    fuego = word_segments(es, "fire")   # fweɣo
    fogo = word_segments(pt, "fire")    # foɡu
    agua_pt = word_segments(pt, "water")  # aɡwa

    cognate_result = align_pair(fuego, fogo)
    unrelated_result = align_pair(fuego, agua_pt)

    assert cognate_result.normalized_score < unrelated_result.normalized_score, (
        f"fuego/fogo ({cognate_result.normalized_score:.3f}) should score better "
        f"than fuego/agua ({unrelated_result.normalized_score:.3f})"
    )


def test_identical_word_scores_zero():
    """A word aligned with itself must produce zero distance."""
    es, _ = parse(ES_CSV, language_name="Spanish")
    fuego = word_segments(es, "fire")
    result = align_pair(fuego, fuego)
    assert result.raw_distance == 0.0


def test_same_gloss_cognate_beats_different_gloss():
    """For each matched-gloss pair, cognate alignment < cross-gloss alignment."""
    es, _ = parse(ES_CSV, language_name="Spanish")
    pt, _ = parse(PT_CSV, language_name="Portuguese")

    for gloss in ("fire", "water"):
        seg_es = word_segments(es, gloss)
        seg_pt_same = word_segments(pt, gloss)
        # pick a different gloss for comparison
        other_gloss = "water" if gloss == "fire" else "son"
        seg_pt_other = word_segments(pt, other_gloss)

        same_result = align_pair(seg_es, seg_pt_same)
        diff_result = align_pair(seg_es, seg_pt_other)

        assert same_result.normalized_score <= diff_result.normalized_score, (
            f"{gloss}: same-gloss score ({same_result.normalized_score:.3f}) "
            f"should be <= cross-gloss score ({diff_result.normalized_score:.3f})"
        )


# ---------------------------------------------------------------------------
# Format test
# ---------------------------------------------------------------------------

def test_format_alignment_output():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    result = align_pair([p, a], [p])
    lines = format_alignment(result).split("\n")
    assert len(lines) == 2
    # Both rows must have the same number of tokens
    assert len(lines[0].split()) == len(lines[1].split())
