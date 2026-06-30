"""Tests for core/gloss_match.py and core/morph_typology.py."""

import pytest
from pathlib import Path
from lingcompare.core.ingest_interlinear import parse as parse_interlinear
from lingcompare.core.gloss_match import (
    propose_tag_correspondences,
    morphemes_for_tag,
    GlossTagMapping,
)
from lingcompare.core.morph_typology import compare_typology

FIXTURES = Path(__file__).parent / "fixtures"


def load_interlinear(name, lang):
    content = (FIXTURES / name).read_text(encoding="utf-8")
    corpus, errors = parse_interlinear(content, language_name=lang)
    return corpus


# ---------------------------------------------------------------------------
# propose_tag_correspondences
# ---------------------------------------------------------------------------

class TestProposeTagCorrespondences:

    def setup_method(self):
        self.es = load_interlinear("es_interlinear.txt", "Spanish")
        self.pt = load_interlinear("pt_interlinear.txt", "Portuguese")

    def test_returns_list_of_mappings(self):
        mappings = propose_tag_correspondences(self.es, self.pt)
        assert isinstance(mappings, list)
        assert all(isinstance(m, GlossTagMapping) for m in mappings)

    def test_pl_plur_proposed(self):
        """PL (ES) and PLUR (PT) are close enough to be proposed."""
        mappings = propose_tag_correspondences(self.es, self.pt)
        tags = {(m.tag_a, m.tag_b) for m in mappings}
        assert ("PL", "PLUR") in tags, f"Expected PL↔PLUR in proposals, got: {tags}"

    def test_sorted_by_score_descending(self):
        mappings = propose_tag_correspondences(self.es, self.pt)
        scores = [m.combined_score for m in mappings]
        assert scores == sorted(scores, reverse=True)

    def test_status_defaults_to_proposed(self):
        mappings = propose_tag_correspondences(self.es, self.pt)
        assert all(m.status == "proposed" for m in mappings)

    def test_empty_when_no_morpheme_breakdowns(self):
        from lingcompare.core.schema import Corpus, Word, Phoneme
        from lingcompare.core.ingest_wordlist import parse as parse_wl
        content = "water,aba\n"
        corpus, _ = parse_wl(content)  # no morpheme breakdown
        mappings = propose_tag_correspondences(corpus, corpus)
        assert mappings == []

    def test_with_glossary_definitions(self):
        """Higher combined score when definitions match."""
        es = load_interlinear("es_interlinear.txt", "Spanish")
        pt = load_interlinear("pt_interlinear.txt", "Portuguese")
        es.gloss_glossary["PL"] = "plural"
        pt.gloss_glossary["PLUR"] = "plural"
        mappings = propose_tag_correspondences(es, pt)
        pl_map = next((m for m in mappings if m.tag_a == "PL"), None)
        assert pl_map is not None
        # Definition similarity should be high since both say "plural"
        assert pl_map.def_similarity > 80


# ---------------------------------------------------------------------------
# morphemes_for_tag
# ---------------------------------------------------------------------------

class TestMorphemesForTag:

    def setup_method(self):
        self.es = load_interlinear("es_interlinear.txt", "Spanish")

    def test_finds_pl_morphemes(self):
        morphs = morphemes_for_tag(self.es, "PL")
        assert len(morphs) > 0

    def test_unknown_tag_returns_empty(self):
        morphs = morphemes_for_tag(self.es, "NONEXISTENT_TAG")
        assert morphs == []

    def test_morpheme_has_segments(self):
        morphs = morphemes_for_tag(self.es, "PL")
        for m in morphs:
            assert len(m.segments) > 0


# ---------------------------------------------------------------------------
# compare_typology
# ---------------------------------------------------------------------------

class TestCompareTypology:

    def setup_method(self):
        self.es = load_interlinear("es_interlinear.txt", "Spanish")
        self.pt = load_interlinear("pt_interlinear.txt", "Portuguese")
        mappings = propose_tag_correspondences(self.es, self.pt)
        # Confirm the PL/PLUR mapping
        for m in mappings:
            if m.tag_a == "PL" and m.tag_b == "PLUR":
                m.status = "confirmed"
        self.mappings = mappings

    def test_returns_list_of_rows(self):
        rows = compare_typology(self.es, self.pt, self.mappings)
        assert isinstance(rows, list)

    def test_pl_plur_row_present(self):
        rows = compare_typology(self.es, self.pt, self.mappings)
        found = any(r.tag_a == "PL" and r.tag_b == "PLUR" for r in rows)
        assert found

    def test_position_profiles_populated(self):
        rows = compare_typology(self.es, self.pt, self.mappings)
        for row in rows:
            assert row.profile_a.language == "Spanish"
            assert row.profile_b.language == "Portuguese"
            assert isinstance(row.profile_a.dominant, str)

    def test_suffix_position_for_pl(self):
        """PL is a suffix in the fixture data (aba-ta → ta is suffix)."""
        rows = compare_typology(self.es, self.pt, self.mappings)
        pl_row = next((r for r in rows if r.tag_a == "PL"), None)
        assert pl_row is not None
        assert pl_row.profile_a.dominant == "suffix"
        assert pl_row.profile_b.dominant == "suffix"

    def test_positions_agree_for_matching_pair(self):
        rows = compare_typology(self.es, self.pt, self.mappings)
        pl_row = next((r for r in rows if r.tag_a == "PL"), None)
        if pl_row:
            assert pl_row.positions_agree()

    def test_note_is_string(self):
        rows = compare_typology(self.es, self.pt, self.mappings)
        for row in rows:
            assert isinstance(row.note(), str)
            assert len(row.note()) > 0

    def test_empty_mappings_returns_empty(self):
        rows = compare_typology(self.es, self.pt, [])
        assert rows == []
