"""Morphological typology comparison.

For each confirmed or proposed gloss-tag correspondence, compares the
position (prefix/suffix/infix/root) of the morphemes carrying those tags in
each corpus. Output is purely descriptive — feeds into the Grammar page as
context for proposed correspondences, not as a probability score.
"""

from __future__ import annotations
from dataclasses import dataclass
from collections import Counter

from .schema import Corpus
from .gloss_match import GlossTagMapping, morphemes_for_tag


@dataclass
class PositionProfile:
    """Position distribution for all morphemes carrying one gloss tag."""
    tag: str
    language: str
    counts: dict[str, int]   # position -> count
    dominant: str            # most common position

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def summary(self) -> str:
        if self.total == 0:
            return "not attested"
        parts = [f"{pos}: {n}" for pos, n in sorted(self.counts.items()) if n > 0]
        return ", ".join(parts) + f" (dominant: {self.dominant})"


@dataclass
class TypologyRow:
    """Comparison of a tag pair's morphological realisation across two corpora."""
    tag_a: str
    tag_b: str
    lang_a: str
    lang_b: str
    profile_a: PositionProfile
    profile_b: PositionProfile

    def positions_agree(self) -> bool:
        return self.profile_a.dominant == self.profile_b.dominant

    def note(self) -> str:
        if self.profile_a.total == 0 and self.profile_b.total == 0:
            return "not attested in either corpus"
        if self.profile_a.total == 0:
            return f"only attested in {self.lang_b}"
        if self.profile_b.total == 0:
            return f"only attested in {self.lang_a}"
        if self.positions_agree():
            return f"both {self.profile_a.dominant}"
        return (
            f"{self.lang_a}: {self.profile_a.dominant}; "
            f"{self.lang_b}: {self.profile_b.dominant} — typological mismatch"
        )


def _position_profile(corpus: Corpus, tag: str) -> PositionProfile:
    morphemes = morphemes_for_tag(corpus, tag)
    counts: Counter[str] = Counter(m.position for m in morphemes)
    dominant = counts.most_common(1)[0][0] if counts else "root"
    return PositionProfile(
        tag=tag,
        language=corpus.language_name,
        counts=dict(counts),
        dominant=dominant,
    )


def compare_typology(
    corpus_a: Corpus,
    corpus_b: Corpus,
    mappings: list[GlossTagMapping],
) -> list[TypologyRow]:
    """Compare morphological positions for a list of tag mappings.

    Args:
        corpus_a: Corpus A with morpheme data.
        corpus_b: Corpus B with morpheme data.
        mappings: Tag mappings (proposed or confirmed) to compare.

    Returns:
        One TypologyRow per mapping, describing the position profiles.
    """
    rows: list[TypologyRow] = []
    for mapping in mappings:
        profile_a = _position_profile(corpus_a, mapping.tag_a)
        profile_b = _position_profile(corpus_b, mapping.tag_b)
        rows.append(TypologyRow(
            tag_a=mapping.tag_a,
            tag_b=mapping.tag_b,
            lang_a=corpus_a.language_name,
            lang_b=corpus_b.language_name,
            profile_a=profile_a,
            profile_b=profile_b,
        ))
    return rows
