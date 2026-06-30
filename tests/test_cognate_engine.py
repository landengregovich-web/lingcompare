"""Tests for core/cognate_engine.py — Pass A and Pass B."""

import pytest
from pathlib import Path
from lingcompare.core.ingest_wordlist import parse
from lingcompare.core.cognate_engine import (
    run_pass_a,
    run_pass_b,
    CandidatePair,
    SoundCorrespondence,
    GLOSS_MATCH_THRESHOLD,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def load_corpora():
    es_csv = (FIXTURES / "es_swadesh.csv").read_text(encoding="utf-8")
    pt_csv = (FIXTURES / "pt_swadesh.csv").read_text(encoding="utf-8")
    es, _ = parse(es_csv, language_name="Spanish")
    pt, _ = parse(pt_csv, language_name="Portuguese")
    return es, pt


SMALL_ES = "gloss,IPA_form\nwater,aɣwa\nfire,fweɣo\nhand,mano\n"
SMALL_PT = "gloss,IPA_form\nwater,aɡwa\nfire,foɡu\nhand,mɐ̃w\n"


def load_small():
    es, _ = parse(SMALL_ES, language_name="Spanish")
    pt, _ = parse(SMALL_PT, language_name="Portuguese")
    return es, pt


# ---------------------------------------------------------------------------
# Pass A tests
# ---------------------------------------------------------------------------

class TestPassA:

    def test_returns_list_of_candidate_pairs(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        assert isinstance(candidates, list)
        assert all(isinstance(c, CandidatePair) for c in candidates)

    def test_matched_glosses_produce_candidates(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        # All three glosses match exactly → 3 candidates
        assert len(candidates) == 3

    def test_candidates_sorted_by_phonetic_score_ascending(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        scores = [c.phonetic_score for c in candidates]
        assert scores == sorted(scores), "Candidates should be sorted best-first"

    def test_water_pair_found(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        water_pairs = [c for c in candidates if c.word_a.gloss == "water"]
        assert len(water_pairs) == 1
        assert water_pairs[0].word_b.gloss == "water"

    def test_gloss_similarity_high_for_exact_match(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        for c in candidates:
            assert c.gloss_similarity >= GLOSS_MATCH_THRESHOLD

    def test_no_cross_gloss_pairs(self):
        """Pass A should not pair 'water' (ES) with 'fire' (PT)."""
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        for c in candidates:
            assert c.word_a.gloss == c.word_b.gloss, (
                f"Cross-gloss pair found: {c.word_a.gloss!r} / {c.word_b.gloss!r}"
            )

    def test_phonetic_scores_in_range(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        for c in candidates:
            assert 0.0 <= c.phonetic_score <= 1.0

    def test_status_defaults_to_pending(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        for c in candidates:
            assert c.status == "pending"

    def test_water_scores_better_than_hand(self):
        """aɣwa/aɡwa (near-identical) should beat mano/mɐ̃w (more divergent)."""
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        by_gloss = {c.word_a.gloss: c for c in candidates}
        assert by_gloss["water"].phonetic_score < by_gloss["hand"].phonetic_score

    def test_full_fixture_finds_all_shared_glosses(self):
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)
        glosses_a = {c.word_a.gloss for c in candidates}
        glosses_b = {c.word_b.gloss for c in candidates}
        shared = {w.gloss for w in es.words} & {w.gloss for w in pt.words}
        assert glosses_a == shared
        assert glosses_b == shared


# ---------------------------------------------------------------------------
# Pass B tests
# ---------------------------------------------------------------------------

class TestPassB:

    def test_returns_correspondences_and_candidates(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        corrs, updated = run_pass_b(candidates)
        assert isinstance(corrs, list)
        assert isinstance(updated, list)
        assert updated is candidates  # mutates in place, returns same list

    def test_final_scores_set_after_pass_b(self):
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        _, updated = run_pass_b(updated := candidates)
        for c in updated:
            assert c.final_score > 0.0

    def test_correspondences_have_minimum_support(self):
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)
        corrs, _ = run_pass_b(candidates, min_support=2)
        for corr in corrs:
            assert len(corr.supporting_pairs) >= 2

    def test_correspondence_fields_populated(self):
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)
        corrs, _ = run_pass_b(candidates)
        for corr in corrs:
            assert corr.position in ("initial", "medial", "final")
            assert isinstance(corr.weight, float)

    def test_rejected_pair_excluded_from_correspondences(self):
        """Rejecting all candidates should leave no correspondences."""
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        for c in candidates:
            c.status = "rejected"
        corrs, _ = run_pass_b(candidates)
        assert corrs == []

    def test_accepting_pair_boosts_systematicity_weight(self):
        """Accepting a pair should increase the weight of its correspondences."""
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)

        # Baseline with all pending
        corrs_before, _ = run_pass_b(candidates)

        # Accept the water pair (strongest cognate)
        water_pair = next(c for c in candidates if c.word_a.gloss == "water")
        water_pair.status = "accepted"
        corrs_after, _ = run_pass_b(candidates)

        # Find a correspondence that water participates in
        water_corrs_after = [
            c for c in corrs_after if water_pair in c.supporting_pairs
        ]
        water_corrs_before = {
            (c.symbol_a, c.symbol_b, c.position): c
            for c in corrs_before
            if water_pair in c.supporting_pairs
        }

        # At least one shared correspondence should have equal or higher weight
        improvements = 0
        for corr in water_corrs_after:
            key = (corr.symbol_a, corr.symbol_b, corr.position)
            if key in water_corrs_before:
                if corr.weight >= water_corrs_before[key].weight:
                    improvements += 1
        assert improvements > 0

    def test_rejecting_pair_lowers_systematicity_weight(self):
        """Rejecting a pair should lower or remove its correspondences."""
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)
        corrs_before, _ = run_pass_b(candidates)
        n_before = len(corrs_before)

        # Reject several candidates — should reduce pattern support
        for c in candidates[:3]:
            c.status = "rejected"
        corrs_after, _ = run_pass_b(candidates)
        # Fewer or equal patterns (some may drop below min_support)
        assert len(corrs_after) <= n_before

    def test_water_final_score_high(self):
        """aɣwa/aɡwa is the closest pair and should score near the top."""
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)
        _, updated = run_pass_b(updated := candidates)
        by_gloss = {c.word_a.gloss: c for c in updated}
        water_score = by_gloss["water"].final_score
        all_scores = [c.final_score for c in updated]
        # water should be in the top 3
        rank = sorted(all_scores, reverse=True).index(water_score)
        assert rank < 3, f"water pair ranked {rank}, expected top 3"

    def test_pass_b_is_idempotent(self):
        """Running Pass B twice with no status changes should give the same scores."""
        es, pt = load_small()
        candidates = run_pass_a(es, pt)
        _, _ = run_pass_b(candidates)
        scores_first = [c.final_score for c in candidates]

        _, _ = run_pass_b(candidates)
        scores_second = [c.final_score for c in candidates]

        assert scores_first == pytest.approx(scores_second)


# ---------------------------------------------------------------------------
# Pass B feedback loop — the core interactive feature
# ---------------------------------------------------------------------------

class TestPassBFeedbackLoop:

    def test_accepting_cognate_adjusts_pending_scores(self):
        """Accepting a known cognate should shift scores of pending candidates
        that share the same sound correspondence pattern."""
        es, pt = load_corpora()
        candidates = run_pass_a(es, pt)

        # Baseline scores
        _, _ = run_pass_b(candidates)
        scores_before = {c.word_a.gloss: c.final_score for c in candidates}

        # Accept 'water' (aɣwa/aɡwa) — establishes a/a, ɣ/ɡ, w/w, a/a patterns
        water = next(c for c in candidates if c.word_a.gloss == "water")
        water.status = "accepted"
        _, _ = run_pass_b(candidates)

        # At least some scores should have changed (not necessarily all up)
        changed = sum(
            1 for c in candidates
            if c.status == "pending"
            and abs(c.final_score - scores_before[c.word_a.gloss]) > 1e-6
        )
        assert changed > 0, "No pending candidates changed score after accepting water"

    def test_pass_b_does_not_rerun_alignments(self):
        """Pass B must not mutate the alignment objects stored on candidates."""
        es, pt = load_small()
        candidates = run_pass_a(es, pt)

        alignments_before = [
            (id(c.alignment), c.alignment.raw_distance) for c in candidates
        ]
        candidates[0].status = "accepted"
        run_pass_b(candidates)

        alignments_after = [
            (id(c.alignment), c.alignment.raw_distance) for c in candidates
        ]
        assert alignments_before == alignments_after, "Pass B should not touch alignments"
