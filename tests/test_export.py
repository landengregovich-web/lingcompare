"""Tests for core/export.py."""

import csv
import io
import json
import pytest
from pathlib import Path

from lingcompare.core.ingest_wordlist import parse as parse_wl
from lingcompare.core.cognate_engine import run_pass_a, run_pass_b
from lingcompare.core.scoring import score_all
from lingcompare.core.export import (
    candidates_csv,
    correspondences_csv,
    full_json,
)
from lingcompare.core.gloss_match import GlossTagMapping

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    content = (FIXTURES / name).read_text(encoding="utf-8")
    corpus, errors = parse_wl(content)
    assert not errors
    return corpus


@pytest.fixture(scope="module")
def es():
    return load("es_swadesh.csv")


@pytest.fixture(scope="module")
def pt():
    return load("pt_swadesh.csv")


@pytest.fixture(scope="module")
def candidates(es, pt):
    return run_pass_a(es, pt)


@pytest.fixture(scope="module")
def correspondences(candidates):
    corrs, _ = run_pass_b(candidates)
    return corrs


@pytest.fixture(scope="module")
def scored(candidates, correspondences, pt):
    return score_all(candidates, correspondences, pt.phoneme_inventory)


# ---------------------------------------------------------------------------
# candidates_csv
# ---------------------------------------------------------------------------

class TestCandidatesCsv:

    def _rows(self, text: str) -> list[dict]:
        return list(csv.DictReader(io.StringIO(text)))

    def test_returns_string(self, candidates, correspondences):
        out = candidates_csv(candidates)
        assert isinstance(out, str)

    def test_row_count(self, candidates, correspondences):
        out = candidates_csv(candidates)
        rows = self._rows(out)
        assert len(rows) == len(candidates)

    def test_has_required_columns(self, candidates):
        out = candidates_csv(candidates, lang_a="ES", lang_b="PT")
        rows = self._rows(out)
        assert rows, "CSV must have at least one data row"
        required = {"status", "gloss_ES", "ipa_ES", "gloss_PT", "ipa_PT",
                    "gloss_similarity", "phonetic_score", "final_score_pass_b",
                    "alignment_a", "alignment_b"}
        assert required <= set(rows[0].keys()), \
            f"Missing: {required - set(rows[0].keys())}"

    def test_status_values_valid(self, candidates):
        out = candidates_csv(candidates)
        rows = self._rows(out)
        for row in rows:
            assert row["status"] in ("accepted", "rejected", "pending")

    def test_scored_columns_included(self, candidates, scored):
        out = candidates_csv(candidates, scored=scored)
        rows = self._rows(out)
        assert "scored_final" in rows[0]
        assert "factor_phonetic" in rows[0]
        assert "factor_systematicity" in rows[0]
        assert "factor_typology" in rows[0]

    def test_scored_columns_absent_without_scored(self, candidates):
        out = candidates_csv(candidates)
        rows = self._rows(out)
        assert "scored_final" not in rows[0]

    def test_accept_reject_reflected(self, candidates, correspondences):
        # Temporarily mutate status
        candidates[0].status = "accepted"
        out = candidates_csv(candidates)
        rows = self._rows(out)
        assert rows[0]["status"] == "accepted"
        candidates[0].status = "pending"  # restore

    def test_alignment_nonempty(self, candidates):
        out = candidates_csv(candidates)
        rows = self._rows(out)
        assert all(row["alignment_a"] for row in rows)

    def test_utf8_ipa_preserved(self, candidates):
        out = candidates_csv(candidates)
        assert any(c in out for c in "ŋɣðθβ")


# ---------------------------------------------------------------------------
# correspondences_csv
# ---------------------------------------------------------------------------

class TestCorrespondencesCsv:

    def _rows(self, text):
        return list(csv.DictReader(io.StringIO(text)))

    def test_returns_string(self, correspondences):
        out = correspondences_csv(correspondences)
        assert isinstance(out, str)

    def test_row_count(self, correspondences):
        out = correspondences_csv(correspondences)
        rows = self._rows(out)
        assert len(rows) == len(correspondences)

    def test_has_required_columns(self, correspondences):
        if not correspondences:
            pytest.skip("No correspondences to test")
        out = correspondences_csv(correspondences)
        rows = self._rows(out)
        required = {"symbol_a", "symbol_b", "position", "weight", "support_count"}
        assert required <= set(rows[0].keys())

    def test_sorted_by_weight_descending(self, correspondences):
        if len(correspondences) < 2:
            pytest.skip("Need 2+ correspondences")
        out = correspondences_csv(correspondences)
        rows = self._rows(out)
        weights = [float(r["weight"]) for r in rows]
        assert weights == sorted(weights, reverse=True)

    def test_empty_correspondences(self):
        out = correspondences_csv([])
        assert "symbol_a" in out  # header row only
        rows = list(csv.DictReader(io.StringIO(out)))
        assert rows == []


# ---------------------------------------------------------------------------
# full_json
# ---------------------------------------------------------------------------

class TestFullJson:

    def _doc(self, es, pt, candidates, correspondences, **kw):
        raw = full_json(es, pt, candidates, correspondences, **kw)
        return json.loads(raw)

    def test_returns_valid_json(self, es, pt, candidates, correspondences):
        raw = full_json(es, pt, candidates, correspondences)
        doc = json.loads(raw)
        assert isinstance(doc, dict)

    def test_meta_fields(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        assert doc["meta"]["lang_a"] == es.language_name
        assert doc["meta"]["lang_b"] == pt.language_name
        assert "exported_at" in doc["meta"]

    def test_candidate_count(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        assert len(doc["candidates"]) == len(candidates)

    def test_correspondences_count(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        assert len(doc["correspondences"]) == len(correspondences)

    def test_candidate_fields(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        c = doc["candidates"][0]
        for field in ("status", "gloss_a", "ipa_a", "gloss_b", "ipa_b",
                      "gloss_similarity", "phonetic_score", "alignment"):
            assert field in c, f"Missing field: {field}"

    def test_alignment_is_dict_with_a_b(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        align = doc["candidates"][0]["alignment"]
        assert "a" in align and "b" in align

    def test_scored_section_included(self, es, pt, candidates, correspondences, scored):
        doc = self._doc(es, pt, candidates, correspondences, scored=scored)
        # At least one candidate should have a scored section
        has_scored = any("scored" in c for c in doc["candidates"])
        assert has_scored

    def test_scored_section_absent_without_scored(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        assert not any("scored" in c for c in doc["candidates"])

    def test_tag_mappings_included(self, es, pt, candidates, correspondences):
        mappings = [
            GlossTagMapping("PL", "PLUR", tag_similarity=80.0,
                            def_similarity=90.0, combined_score=86.0, status="confirmed")
        ]
        doc = self._doc(es, pt, candidates, correspondences, tag_mappings=mappings)
        assert "tag_mappings" in doc
        assert len(doc["tag_mappings"]) == 1
        assert doc["tag_mappings"][0]["tag_a"] == "PL"

    def test_tag_mappings_absent_when_none(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences, tag_mappings=None)
        assert "tag_mappings" not in doc

    def test_phoneme_inventories_present(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        inv = doc["phoneme_inventories"]
        assert es.language_name in inv
        assert pt.language_name in inv
        assert isinstance(inv[es.language_name], list)

    def test_ipa_chars_not_escaped(self, es, pt, candidates, correspondences):
        raw = full_json(es, pt, candidates, correspondences)
        # ensure_ascii=False means IPA symbols appear literally
        assert "\\u" not in raw or any(c in raw for c in "ŋɣðθ")

    def test_exported_at_is_iso8601(self, es, pt, candidates, correspondences):
        doc = self._doc(es, pt, candidates, correspondences)
        ts = doc["meta"]["exported_at"]
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None
