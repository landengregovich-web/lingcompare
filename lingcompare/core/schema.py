"""Core data model for LingCompare. Zero Streamlit dependency."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

import panphon

_ft = panphon.FeatureTable()


@dataclass(frozen=True)
class Phoneme:
    """A single IPA segment with its phonetic feature vector.

    frozen=True so Phoneme is hashable and can live in sets/dicts as a key.
    """
    ipa_symbol: str
    # Tuple of (feature_name, value) pairs — immutable so Phoneme stays hashable.
    # Values are ints: +1, 0, or -1 (PanPhon convention).
    features: tuple[tuple[str, int], ...]

    def __repr__(self) -> str:
        return f"Phoneme({self.ipa_symbol!r})"

    def feature_dict(self) -> dict[str, int]:
        return dict(self.features)

    def panphon_segment(self):
        """Return the live panphon Segment for distance calculations."""
        return _ft.fts(self.ipa_symbol)

    @staticmethod
    def from_ipa(symbol: str) -> "Phoneme":
        """Construct a Phoneme from a single IPA token string.

        PanPhon 0.22+ API: fts() returns a Segment object or {} (empty dict)
        when the symbol is unrecognized.

        Raises ValueError with the Unicode codepoint if symbol is unknown.
        """
        seg = _ft.fts(symbol)
        if not seg:  # empty dict {} means unrecognized
            codepoints = " ".join(f"U+{ord(c):04X}" for c in symbol)
            raise ValueError(
                f"Unknown IPA symbol {symbol!r} ({codepoints}). "
                "Check that the character is a valid IPA segment."
            )
        feat_tuple = tuple(sorted(seg.items()))
        return Phoneme(ipa_symbol=symbol, features=feat_tuple)


MorphemePosition = Literal["prefix", "suffix", "infix", "root", "other"]


@dataclass
class Morpheme:
    """A morpheme: a sequence of phonemes carrying a grammatical or lexical gloss."""
    segments: list[Phoneme]
    gloss_tag: str                        # user-defined, corpus-specific
    position: MorphemePosition = "root"

    @property
    def ipa(self) -> str:
        return "".join(p.ipa_symbol for p in self.segments)


@dataclass
class Word:
    """A lexical entry: a gloss, its full phonemic form, and optional morpheme breakdown."""
    gloss: str
    segments: list[Phoneme]               # full phonemic form
    morphemes: list[Morpheme] = field(default_factory=list)  # empty = unanalyzed

    @property
    def ipa(self) -> str:
        return "".join(p.ipa_symbol for p in self.segments)

    def __repr__(self) -> str:
        return f"Word({self.gloss!r}, /{self.ipa}/)"


@dataclass
class Corpus:
    """A collection of words for one language, plus the user-defined gloss glossary."""
    language_name: str
    words: list[Word] = field(default_factory=list)
    gloss_glossary: dict[str, str] = field(default_factory=dict)  # tag -> meaning

    @property
    def phoneme_inventory(self) -> set[Phoneme]:
        """Derived from words — never set directly."""
        inv: set[Phoneme] = set()
        for word in self.words:
            inv.update(word.segments)
        return inv


def tokenize_ipa(ipa_string: str) -> list[str]:
    """Tokenize an IPA string into segment tokens using PanPhon's trie.

    PanPhon's ipa_segs() handles digraphs and diacritics correctly.
    Returns only segments PanPhon recognizes; unrecognized characters are
    silently dropped (the caller validates with from_ipa to surface errors).
    """
    return _ft.ipa_segs(ipa_string)
