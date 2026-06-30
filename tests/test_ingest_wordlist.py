"""Tests for core/ingest_wordlist.py."""

import pytest
from pathlib import Path
from lingcompare.core.ingest_wordlist import parse, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_valid_csv():
    content = "gloss,IPA_form\nwater,aɡwa\nfire,fweɣo\n"
    corpus, errors = parse(content, language_name="Spanish")
    assert errors == []
    assert len(corpus.words) == 2
    assert corpus.words[0].gloss == "water"
    assert corpus.words[1].gloss == "fire"
    assert corpus.language_name == "Spanish"


def test_parse_header_auto_detect():
    # No header row
    content = "water,aɡwa\nfire,fweɣo\n"
    corpus, errors = parse(content)
    assert errors == []
    assert len(corpus.words) == 2


def test_parse_phonemes_populated():
    content = "water,aba\n"
    corpus, errors = parse(content)
    assert errors == []
    word = corpus.words[0]
    assert len(word.segments) == 3
    assert word.ipa == "aba"


def test_parse_invalid_ipa_character_raises_error():
    content = "water,aQa\n"  # Q is not a valid IPA symbol
    corpus, errors = parse(content)
    assert len(errors) >= 1
    assert any("Q" in e.message for e in errors)
    assert errors[0].row == 1
    assert errors[0].column == "IPA_form"


def test_parse_error_includes_row_number():
    content = "word1,aba\nword2,aQa\nword3,aba\n"
    corpus, errors = parse(content)
    assert any(e.row == 2 for e in errors)
    # word1 and word3 should still parse
    assert len(corpus.words) == 2


def test_parse_empty_gloss_error():
    content = ",aba\n"
    corpus, errors = parse(content)
    assert any("empty" in e.message.lower() for e in errors)


def test_parse_missing_ipa_column_error():
    content = "water\n"
    corpus, errors = parse(content)
    assert any("two columns" in e.message for e in errors)


def test_parse_morpheme_breakdown():
    content = "waters,abata,aba-ta\n"
    corpus, errors = parse(content)
    assert errors == []
    word = corpus.words[0]
    assert len(word.morphemes) == 2
    assert word.morphemes[0].ipa == "aba"
    assert word.morphemes[1].ipa == "ta"


def test_parse_breakdown_mismatch_error():
    content = "waters,abata,aba-xx\n"  # xx doesn't match 'ta'
    corpus, errors = parse(content)
    assert any("morpheme_breakdown" in e.column for e in errors)


def test_parse_spanish_fixture():
    content = (FIXTURES / "es_swadesh.csv").read_text(encoding="utf-8")
    corpus, errors = parse(content, language_name="Spanish")
    # Allow some errors for exotic IPA chars, but most words should parse
    assert len(corpus.words) >= 10, f"Only {len(corpus.words)} words parsed; errors: {errors}"


def test_parse_portuguese_fixture():
    content = (FIXTURES / "pt_swadesh.csv").read_text(encoding="utf-8")
    corpus, errors = parse(content, language_name="Portuguese")
    assert len(corpus.words) >= 10, f"Only {len(corpus.words)} words parsed; errors: {errors}"


def test_phoneme_inventory_derived_from_words():
    content = "water,aba\n"
    corpus, _ = parse(content)
    inv = corpus.phoneme_inventory
    symbols = {p.ipa_symbol for p in inv}
    assert "a" in symbols
    assert "b" in symbols
