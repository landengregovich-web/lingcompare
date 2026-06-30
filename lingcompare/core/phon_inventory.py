"""Phoneme inventory extraction and comparison.

Extracts the phoneme inventory actually present in a corpus, classifies each
phoneme into a natural class, and produces a descriptive comparison of two
inventories. Output is always descriptive — no probability scores.
"""

from __future__ import annotations
from dataclasses import dataclass

from .schema import Corpus, Phoneme, _ft

# Features to display in the UI — the full 24-feature vector is noise.
DISPLAY_FEATURES = ["syl", "son", "cons", "cont", "nas", "lat", "voi", "lab", "cor", "hi", "lo", "back", "round"]


@dataclass
class InventoryComparison:
    shared: set[Phoneme]
    only_in_a: set[Phoneme]
    only_in_b: set[Phoneme]


def extract_inventory(corpus: Corpus) -> dict[str, Phoneme]:
    """Return {ipa_symbol: Phoneme} for all phonemes present in the corpus."""
    return {p.ipa_symbol: p for p in corpus.phoneme_inventory}


def compare_inventories(
    inv_a: dict[str, Phoneme],
    inv_b: dict[str, Phoneme],
) -> InventoryComparison:
    syms_a = set(inv_a)
    syms_b = set(inv_b)
    shared_syms = syms_a & syms_b
    return InventoryComparison(
        shared={inv_a[s] for s in shared_syms},
        only_in_a={inv_a[s] for s in syms_a - syms_b},
        only_in_b={inv_b[s] for s in syms_b - syms_a},
    )


def natural_class(phoneme: Phoneme) -> str:
    """Return a human-readable natural class label for a phoneme."""
    d = phoneme.feature_dict()

    if d.get("syl") == 1:
        # Vowel sub-classification
        height = "low" if d.get("lo") == 1 else ("high" if d.get("hi") == 1 else "mid")
        backness = "back" if d.get("back") == 1 else "front"
        rounding = ", rounded" if d.get("round") == 1 else ""
        nasality = ", nasal" if d.get("nas") == 1 else ""
        return f"vowel ({height} {backness}{rounding}{nasality})"

    # Consonant sub-classification
    parts = []

    voicing = "voiced" if d.get("voi") == 1 else "voiceless"
    parts.append(voicing)

    # Place
    if d.get("lab") == 1 and d.get("cor") != 1:
        place = "labial"
    elif d.get("lab") == 1 and d.get("cor") == 1:
        place = "labio-dental"
    elif d.get("cor") == 1 and d.get("ant") == 1 if "ant" in d else d.get("cor") == 1:
        place = "coronal"
    elif d.get("hi") == 1 and d.get("back") == -1:
        place = "palatal"
    elif d.get("hi") == 1 and d.get("back") == 1:
        place = "velar"
    elif d.get("lo") == -1 and d.get("back") == 1:
        place = "uvular"
    else:
        place = "other"
    parts.append(place)

    # Manner
    if d.get("nas") == 1:
        manner = "nasal"
    elif d.get("lat") == 1:
        manner = "lateral"
    elif d.get("son") == 1:
        manner = "approximant"
    elif d.get("cont") == 1:
        manner = "fricative"
    elif d.get("delrel") == 1 if "delrel" in d else False:
        manner = "affricate"
    else:
        manner = "stop"
    parts.append(manner)

    return " ".join(parts)


def phoneme_feature_row(phoneme: Phoneme) -> dict:
    """Return a display-ready dict of selected features for a phoneme."""
    d = phoneme.feature_dict()
    val_str = {1: "+", 0: "0", -1: "−"}
    row = {"IPA": phoneme.ipa_symbol, "class": natural_class(phoneme)}
    for feat in DISPLAY_FEATURES:
        row[feat] = val_str.get(d.get(feat, 0), "?")
    return row


def inventory_to_rows(inv: dict[str, Phoneme]) -> list[dict]:
    """Convert an inventory dict to a list of display rows, sorted by class then IPA."""
    rows = [phoneme_feature_row(p) for p in inv.values()]
    return sorted(rows, key=lambda r: (r["class"], r["IPA"]))
