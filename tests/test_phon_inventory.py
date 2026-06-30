"""Tests for core/phon_inventory.py."""

import pytest
from pathlib import Path
from lingcompare.core.ingest_wordlist import parse
from lingcompare.core.phon_inventory import (
    extract_inventory,
    compare_inventories,
    natural_class,
    inventory_to_rows,
    phoneme_feature_row,
    DISPLAY_FEATURES,
)
from lingcompare.core.schema import Phoneme

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str, lang: str):
    csv = (FIXTURES / name).read_text(encoding="utf-8")
    corpus, errors = parse(csv, language_name=lang)
    assert not errors, f"Fixture errors: {errors}"
    return corpus


# ---------------------------------------------------------------------------
# extract_inventory
# ---------------------------------------------------------------------------

class TestExtractInventory:

    def test_returns_dict_keyed_by_ipa_symbol(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        assert isinstance(inv, dict)
        assert all(isinstance(k, str) for k in inv)
        assert all(isinstance(v, Phoneme) for v in inv.values())

    def test_inventory_non_empty(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        assert len(inv) > 0

    def test_known_phonemes_present(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        # Spanish fixture has /a/, /n/, /m/ in multiple words
        assert "a" in inv
        assert "n" in inv

    def test_keys_match_phoneme_symbols(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        for sym, phoneme in inv.items():
            assert sym == phoneme.ipa_symbol

    def test_no_duplicates(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        assert len(inv) == len(set(inv.keys()))


# ---------------------------------------------------------------------------
# compare_inventories
# ---------------------------------------------------------------------------

class TestCompareInventories:

    def setup_method(self):
        self.es = load_fixture("es_swadesh.csv", "Spanish")
        self.pt = load_fixture("pt_swadesh.csv", "Portuguese")
        self.inv_a = extract_inventory(self.es)
        self.inv_b = extract_inventory(self.pt)
        self.comp = compare_inventories(self.inv_a, self.inv_b)

    def test_shared_is_intersection(self):
        shared_syms = {p.ipa_symbol for p in self.comp.shared}
        expected = set(self.inv_a) & set(self.inv_b)
        assert shared_syms == expected

    def test_only_a_not_in_b(self):
        for p in self.comp.only_in_a:
            assert p.ipa_symbol not in self.inv_b

    def test_only_b_not_in_a(self):
        for p in self.comp.only_in_b:
            assert p.ipa_symbol not in self.inv_a

    def test_partition_covers_all(self):
        all_a = set(self.inv_a)
        all_b = set(self.inv_b)
        shared_syms = {p.ipa_symbol for p in self.comp.shared}
        only_a_syms = {p.ipa_symbol for p in self.comp.only_in_a}
        only_b_syms = {p.ipa_symbol for p in self.comp.only_in_b}
        assert shared_syms | only_a_syms == all_a
        assert shared_syms | only_b_syms == all_b

    def test_sets_are_disjoint(self):
        shared_syms = {p.ipa_symbol for p in self.comp.shared}
        only_a_syms = {p.ipa_symbol for p in self.comp.only_in_a}
        only_b_syms = {p.ipa_symbol for p in self.comp.only_in_b}
        assert shared_syms.isdisjoint(only_a_syms)
        assert shared_syms.isdisjoint(only_b_syms)

    def test_identical_inventories_all_shared(self):
        inv = extract_inventory(self.es)
        comp = compare_inventories(inv, inv)
        assert len(comp.only_in_a) == 0
        assert len(comp.only_in_b) == 0
        assert len(comp.shared) == len(inv)


# ---------------------------------------------------------------------------
# natural_class
# ---------------------------------------------------------------------------

class TestNaturalClass:

    def test_vowel_classified_as_vowel(self):
        a = Phoneme.from_ipa("a")
        assert "vowel" in natural_class(a)

    def test_stop_classified(self):
        p = Phoneme.from_ipa("p")
        label = natural_class(p)
        assert "stop" in label

    def test_nasal_classified(self):
        n = Phoneme.from_ipa("n")
        label = natural_class(n)
        assert "nasal" in label

    def test_fricative_classified(self):
        s = Phoneme.from_ipa("s")
        label = natural_class(s)
        assert "fricative" in label

    def test_voiced_stop(self):
        b = Phoneme.from_ipa("b")
        label = natural_class(b)
        assert "voiced" in label
        assert "stop" in label

    def test_voiceless_stop(self):
        p = Phoneme.from_ipa("p")
        label = natural_class(p)
        assert "voiceless" in label

    def test_returns_string(self):
        for sym in ["p", "a", "n", "s", "l", "k"]:
            ph = Phoneme.from_ipa(sym)
            assert isinstance(natural_class(ph), str)
            assert len(natural_class(ph)) > 0


# ---------------------------------------------------------------------------
# phoneme_feature_row and inventory_to_rows
# ---------------------------------------------------------------------------

class TestDisplayRows:

    def test_feature_row_has_ipa_key(self):
        p = Phoneme.from_ipa("p")
        row = phoneme_feature_row(p)
        assert row["IPA"] == "p"
        assert "class" in row

    def test_feature_row_has_display_features(self):
        p = Phoneme.from_ipa("p")
        row = phoneme_feature_row(p)
        for feat in DISPLAY_FEATURES:
            assert feat in row, f"Feature {feat!r} missing from display row"

    def test_feature_values_are_strings(self):
        p = Phoneme.from_ipa("p")
        row = phoneme_feature_row(p)
        for feat in DISPLAY_FEATURES:
            assert row[feat] in ("+", "0", "−"), f"Unexpected value {row[feat]!r} for {feat}"

    def test_inventory_to_rows_sorted(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        rows = inventory_to_rows(inv)
        # Sorted by (class, IPA)
        keys = [(r["class"], r["IPA"]) for r in rows]
        assert keys == sorted(keys)

    def test_inventory_to_rows_count_matches_inventory(self):
        corpus = load_fixture("es_swadesh.csv", "Spanish")
        inv = extract_inventory(corpus)
        rows = inventory_to_rows(inv)
        assert len(rows) == len(inv)
