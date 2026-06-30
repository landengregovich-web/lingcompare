"""Tests for core/scoring.py."""

import pytest
from pathlib import Path

from lingcompare.core.ingest_wordlist import parse as parse_wl
from lingcompare.core.cognate_engine import run_pass_a, run_pass_b
from lingcompare.core.scoring import (
    sound_change_plausibility,
    compute_scored_evidence,
    score_all,
    WEIGHTS,
    ScoredEvidence,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_corpus(name):
    content = (FIXTURES / name).read_text(encoding="utf-8")
    corpus, errors = parse_wl(content)
    assert errors == [], f"Parse errors: {errors}"
    return corpus


@pytest.fixture(scope="module")
def es_corpus():
    return load_corpus("es_swadesh.csv")


@pytest.fixture(scope="module")
def pt_corpus():
    return load_corpus("pt_swadesh.csv")


@pytest.fixture(scope="module")
def candidates(es_corpus, pt_corpus):
    return run_pass_a(es_corpus, pt_corpus)


@pytest.fixture(scope="module")
def correspondences(candidates):
    corrs, _ = run_pass_b(candidates)
    return corrs


# ---------------------------------------------------------------------------
# sound_change_plausibility
# ---------------------------------------------------------------------------

class TestSoundChangePlausibility:

    def test_identity_is_1(self):
        assert sound_change_plausibility("a", "a") == 1.0
        assert sound_change_plausibility("k", "k") == 1.0

    def test_gap_returns_half(self):
        assert sound_change_plausibility(None, "a") == 0.50
        assert sound_change_plausibility("a", None) == 0.50

    def test_both_none_returns_half(self):
        assert sound_change_plausibility(None, None) == 0.50

    def test_lenition_b_v_high(self):
        assert sound_change_plausibility("b", "v") >= 0.75

    def test_spirantization_d_eth_high(self):
        assert sound_change_plausibility("d", "ð") >= 0.80

    def test_grimm_p_f_high(self):
        assert sound_change_plausibility("p", "f") >= 0.85

    def test_unusual_change_low(self):
        plaus = sound_change_plausibility("a", "k")  # vowel-to-stop — very unusual
        assert plaus <= 0.40

    def test_symmetric_lookup(self):
        # Table has b→v but not v→b explicitly; should still return something reasonable
        assert sound_change_plausibility("v", "b") > 0.50

    def test_voicing_pair(self):
        assert sound_change_plausibility("p", "b") >= 0.75

    def test_liquid_shift(self):
        assert sound_change_plausibility("l", "r") >= 0.60


# ---------------------------------------------------------------------------
# compute_scored_evidence
# ---------------------------------------------------------------------------

class TestComputeScoredEvidence:

    def test_returns_scored_evidence(self, candidates, correspondences, pt_corpus):
        pair = candidates[0]
        evidence = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory)
        assert isinstance(evidence, ScoredEvidence)

    def test_final_score_in_range(self, candidates, correspondences, pt_corpus):
        for pair in candidates[:5]:
            ev = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory)
            assert 0.0 <= ev.final_score <= 1.0, f"final_score out of range: {ev.final_score}"

    def test_all_factors_present(self, candidates, correspondences, pt_corpus):
        ev = compute_scored_evidence(candidates[0], correspondences, pt_corpus.phoneme_inventory)
        assert set(ev.factor_scores.keys()) == set(WEIGHTS.keys())

    def test_all_factor_scores_in_range(self, candidates, correspondences, pt_corpus):
        ev = compute_scored_evidence(candidates[0], correspondences, pt_corpus.phoneme_inventory)
        for k, v in ev.factor_scores.items():
            assert 0.0 <= v <= 1.0, f"factor {k} out of range: {v}"

    def test_weights_sum_to_1(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_final_score_matches_weighted_sum(self, candidates, correspondences, pt_corpus):
        ev = compute_scored_evidence(candidates[0], correspondences, pt_corpus.phoneme_inventory)
        expected = sum(WEIGHTS[k] * ev.factor_scores[k] for k in WEIGHTS)
        assert abs(ev.final_score - expected) < 1e-9

    def test_narrative_is_nonempty_string(self, candidates, correspondences, pt_corpus):
        ev = compute_scored_evidence(candidates[0], correspondences, pt_corpus.phoneme_inventory)
        assert isinstance(ev.narrative, str)
        assert len(ev.narrative) > 20

    def test_gloss_support_raises_gloss_factor(self, candidates, correspondences, pt_corpus):
        pair = candidates[0]
        ev_no_sup = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory,
                                            gloss_support=0.0)
        ev_full_sup = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory,
                                              gloss_support=1.0)
        assert ev_full_sup.factor_scores["gloss"] >= ev_no_sup.factor_scores["gloss"]

    def test_high_gloss_support_raises_final_score(self, candidates, correspondences, pt_corpus):
        pair = candidates[0]
        ev_no = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory,
                                        gloss_support=0.0)
        ev_yes = compute_scored_evidence(pair, correspondences, pt_corpus.phoneme_inventory,
                                         gloss_support=1.0)
        assert ev_yes.final_score >= ev_no.final_score

    def test_empty_inventory_half_score(self, candidates, correspondences):
        pair = candidates[0]
        ev = compute_scored_evidence(pair, correspondences, inventory_b=set())
        assert ev.factor_scores["inventory"] == 0.5


# ---------------------------------------------------------------------------
# score_all
# ---------------------------------------------------------------------------

class TestScoreAll:

    def test_score_all_returns_same_length(self, candidates, correspondences, pt_corpus):
        results = score_all(candidates, correspondences, pt_corpus.phoneme_inventory)
        assert len(results) == len(candidates)

    def test_all_are_scored_evidence(self, candidates, correspondences, pt_corpus):
        results = score_all(candidates, correspondences, pt_corpus.phoneme_inventory)
        assert all(isinstance(r, ScoredEvidence) for r in results)

    def test_pair_reference_preserved(self, candidates, correspondences, pt_corpus):
        results = score_all(candidates, correspondences, pt_corpus.phoneme_inventory)
        for r, c in zip(results, candidates):
            assert r.pair is c
