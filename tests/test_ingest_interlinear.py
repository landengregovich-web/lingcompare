"""Tests for core/ingest_interlinear.py."""

import pytest
from pathlib import Path
from lingcompare.core.ingest_interlinear import parse

FIXTURES = Path(__file__).parent / "fixtures"

SIMPLE = """\
IPA:   aba-ta
GLOSS: water-PL
TRANS: waters
"""

TWO_WORDS = """\
IPA:   aba kela
GLOSS: water big
TRANS: big water
"""

MULTI_BLOCK = """\
IPA:   aba-ta
GLOSS: water-PL
TRANS: waters

IPA:   mano
GLOSS: hand
TRANS: hand
"""

BAD_COUNT = """\
IPA:   aba ta
GLOSS: water
"""

MORPH_MISMATCH = """\
IPA:   aba-ta-ke
GLOSS: water-PL
"""


class TestParseBasic:

    def test_single_morpheme_word(self):
        corpus, errors = parse("IPA: aba\nGLOSS: water\n", language_name="Test")
        assert errors == []
        assert len(corpus.words) == 1
        assert corpus.words[0].gloss == "water"

    def test_morpheme_split(self):
        corpus, errors = parse(SIMPLE, language_name="Test")
        assert errors == []
        word = corpus.words[0]
        assert len(word.morphemes) == 2
        assert word.morphemes[0].gloss_tag == "water"
        assert word.morphemes[1].gloss_tag == "PL"

    def test_morpheme_positions(self):
        corpus, errors = parse(SIMPLE)
        assert errors == []
        morphemes = corpus.words[0].morphemes
        assert morphemes[0].position == "prefix"
        assert morphemes[1].position == "suffix"

    def test_trans_used_as_word_gloss(self):
        corpus, errors = parse(SIMPLE)
        assert errors == []
        assert corpus.words[0].gloss == "waters"

    def test_two_words_in_block(self):
        corpus, errors = parse(TWO_WORDS)
        assert errors == []
        assert len(corpus.words) == 2

    def test_multiple_blocks(self):
        corpus, errors = parse(MULTI_BLOCK)
        assert errors == []
        assert len(corpus.words) == 2

    def test_segments_populated(self):
        corpus, errors = parse("IPA: aba\nGLOSS: water\n")
        assert errors == []
        assert len(corpus.words[0].segments) == 3  # a, b, a

    def test_language_name_set(self):
        corpus, errors = parse("IPA: aba\nGLOSS: water\n", language_name="TestLang")
        assert corpus.language_name == "TestLang"

    def test_gloss_glossary_passed_through(self):
        corpus, errors = parse(
            "IPA: aba\nGLOSS: water\n",
            gloss_glossary={"PL": "plural"},
        )
        assert corpus.gloss_glossary == {"PL": "plural"}

    def test_case_insensitive_labels(self):
        corpus, errors = parse("ipa: aba\ngloss: water\n")
        assert errors == []
        assert len(corpus.words) == 1

    def test_fixture_es(self):
        content = (FIXTURES / "es_interlinear.txt").read_text(encoding="utf-8")
        corpus, errors = parse(content, language_name="Spanish")
        assert len(corpus.words) >= 4, f"Expected ≥4 words, got {len(corpus.words)}; errors: {errors}"

    def test_fixture_pt(self):
        content = (FIXTURES / "pt_interlinear.txt").read_text(encoding="utf-8")
        corpus, errors = parse(content, language_name="Portuguese")
        assert len(corpus.words) >= 4


class TestParseErrors:

    def test_word_count_mismatch_error(self):
        _, errors = parse(BAD_COUNT)
        assert len(errors) >= 1
        assert any("IPA" in e.column and "GLOSS" in e.column for e in errors)

    def test_morpheme_count_mismatch_error(self):
        _, errors = parse(MORPH_MISMATCH)
        assert len(errors) >= 1

    def test_missing_ipa_line_error(self):
        _, errors = parse("GLOSS: water\n")
        assert any("IPA" in e.message for e in errors)

    def test_missing_gloss_line_error(self):
        _, errors = parse("IPA: aba\n")
        assert any("GLOSS" in e.message for e in errors)

    def test_invalid_ipa_char_error(self):
        _, errors = parse("IPA: aQa\nGLOSS: water\n")
        assert len(errors) >= 1
        assert any("Q" in e.message for e in errors)

    def test_valid_block_after_bad_block_still_parsed(self):
        content = "GLOSS: water\n\nIPA: aba\nGLOSS: water\n"
        corpus, errors = parse(content)
        assert len(errors) >= 1
        assert len(corpus.words) == 1  # second block parsed ok
