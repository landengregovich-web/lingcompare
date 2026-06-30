"""Fuzzy gloss-tag correspondence proposals.

Proposes candidate correspondences between user-defined gloss tags in corpus A
and corpus B using rapidfuzz string similarity on tag labels and glossary
definitions. Never assumes tags mean the same thing — proposals are always
candidates, not assertions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from .schema import Corpus, Morpheme

GlossTagStatus = Literal["proposed", "confirmed", "rejected"]

# Weight of tag-string similarity vs. definition similarity.
# Definitions are more semantically informative, so they get higher weight
# when the user has provided them.
TAG_WEIGHT: float = 0.4
DEF_WEIGHT: float = 0.6

# Minimum combined similarity (0–100) to propose a correspondence.
DEFAULT_THRESHOLD: float = 55.0


@dataclass
class GlossTagMapping:
    """A proposed or confirmed correspondence between gloss tags in A and B."""
    tag_a: str
    tag_b: str
    tag_similarity: float       # rapidfuzz ratio on tag strings, 0–100
    def_similarity: float       # rapidfuzz ratio on glossary definitions, 0–100
    combined_score: float       # weighted combination, 0–100
    status: GlossTagStatus = "proposed"

    def label(self) -> str:
        return f"{self.tag_a} ↔ {self.tag_b}"


def _collect_tags(corpus: Corpus) -> set[str]:
    """Return all gloss tags used in the corpus's morpheme breakdowns."""
    tags: set[str] = set()
    for word in corpus.words:
        for morph in word.morphemes:
            if morph.gloss_tag:
                tags.add(morph.gloss_tag)
    return tags


def propose_tag_correspondences(
    corpus_a: Corpus,
    corpus_b: Corpus,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[GlossTagMapping]:
    """Propose candidate gloss-tag correspondences between two corpora.

    Args:
        corpus_a: Corpus with morpheme breakdowns.
        corpus_b: Corpus with morpheme breakdowns.
        threshold: Minimum combined similarity score to propose (0–100).

    Returns:
        List of GlossTagMapping objects sorted by combined_score descending.
        Empty if neither corpus has morpheme breakdowns.
    """
    tags_a = _collect_tags(corpus_a)
    tags_b = _collect_tags(corpus_b)

    if not tags_a or not tags_b:
        return []

    glossary_a = corpus_a.gloss_glossary  # tag -> meaning
    glossary_b = corpus_b.gloss_glossary

    mappings: list[GlossTagMapping] = []

    for tag_a in sorted(tags_a):
        best: GlossTagMapping | None = None

        for tag_b in sorted(tags_b):
            tag_sim = fuzz.ratio(tag_a.lower(), tag_b.lower())

            # Definition similarity: only meaningful when both have glossary entries
            def_a = glossary_a.get(tag_a, "")
            def_b = glossary_b.get(tag_b, "")
            if def_a and def_b:
                def_sim = fuzz.ratio(def_a.lower(), def_b.lower())
                combined = TAG_WEIGHT * tag_sim + DEF_WEIGHT * def_sim
            else:
                # No definitions: fall back to tag similarity only
                def_sim = 0.0
                combined = tag_sim

            if combined < threshold:
                continue

            candidate = GlossTagMapping(
                tag_a=tag_a,
                tag_b=tag_b,
                tag_similarity=tag_sim,
                def_similarity=def_sim,
                combined_score=combined,
            )

            if best is None or combined > best.combined_score:
                best = candidate

        if best is not None:
            mappings.append(best)

    mappings.sort(key=lambda m: -m.combined_score)
    return mappings


def morphemes_for_tag(corpus: Corpus, tag: str) -> list[Morpheme]:
    """Return all Morpheme objects in the corpus carrying a given gloss tag."""
    result: list[Morpheme] = []
    for word in corpus.words:
        for morph in word.morphemes:
            if morph.gloss_tag == tag:
                result.append(morph)
    return result
