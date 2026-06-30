"""Tests for core/schema.py."""

import pytest
from lingcompare.core.schema import Phoneme, Morpheme, Word, Corpus


def test_phoneme_from_ipa_known_symbol():
    p = Phoneme.from_ipa("p")
    assert p.ipa_symbol == "p"
    assert isinstance(p.features, tuple)
    assert len(p.features) > 0


def test_phoneme_from_ipa_unknown_raises():
    with pytest.raises(ValueError, match="Unknown IPA symbol"):
        Phoneme.from_ipa("Q")  # not a valid IPA segment


def test_phoneme_hashable_and_eq():
    p1 = Phoneme.from_ipa("p")
    p2 = Phoneme.from_ipa("p")
    assert p1 == p2
    assert hash(p1) == hash(p2)
    s = {p1, p2}
    assert len(s) == 1


def test_phoneme_set_distinct():
    p = Phoneme.from_ipa("p")
    b = Phoneme.from_ipa("b")
    assert p != b
    assert {p, b} == {p, b}
    assert len({p, b}) == 2


def test_corpus_phoneme_inventory_derived():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    word = Word(gloss="pa", segments=[p, a])
    corpus = Corpus(language_name="TestLang", words=[word])
    inv = corpus.phoneme_inventory
    assert p in inv
    assert a in inv
    assert len(inv) == 2


def test_corpus_phoneme_inventory_deduplicates():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    w1 = Word(gloss="pa", segments=[p, a])
    w2 = Word(gloss="ap", segments=[a, p])
    corpus = Corpus(language_name="TestLang", words=[w1, w2])
    assert len(corpus.phoneme_inventory) == 2


def test_word_ipa_property():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    word = Word(gloss="pa", segments=[p, a])
    assert word.ipa == "pa"


def test_morpheme_ipa_property():
    p = Phoneme.from_ipa("p")
    a = Phoneme.from_ipa("a")
    m = Morpheme(segments=[p, a], gloss_tag="ROOT")
    assert m.ipa == "pa"
