"""Cognate detection engine: Pass A (semantic-anchored alignment) and
Pass B (systematicity detection + feedback loop).

Pass A runs once per corpus pair and is expensive (O(n*m) alignments).
Pass B reruns cheaply on every user accept/reject decision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from .schema import Corpus, Phoneme, Word
from .phon_align import AlignmentResult, align_pair

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Minimum rapidfuzz ratio (0–100) for two glosses to be considered semantically
# anchored. 85 allows minor spelling variation ("to do" / "do") without
# collapsing semantically distinct glosses.
GLOSS_MATCH_THRESHOLD: float = 85.0

# Minimum number of independent word pairs that must exhibit a sound
# correspondence before it is counted as "systematic."
MIN_SUPPORT: int = 2

# How accepted/rejected pairs weight the systematicity score.
ACCEPTED_WEIGHT: float = 2.0
PENDING_WEIGHT: float = 1.0
REJECTED_WEIGHT: float = -3.0

# Combination weights for the final score.
PHONETIC_ALPHA: float = 0.6
SYSTEMATICITY_BETA: float = 0.4

CandidateStatus = Literal["pending", "accepted", "rejected"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidatePair:
    """A proposed word-level correspondence between corpora A and B."""
    word_a: Word
    word_b: Word
    gloss_similarity: float           # rapidfuzz ratio, 0–100
    alignment: AlignmentResult
    phonetic_score: float             # normalised alignment distance, lower = better match
    systematicity_bonus: float = 0.0  # set by Pass B
    final_score: float = 0.0         # set by Pass B (or equals phonetic_score before B runs)
    status: CandidateStatus = "pending"

    def __post_init__(self) -> None:
        if self.final_score == 0.0:
            # Before Pass B runs, seed final_score from phonetics alone
            self.final_score = 1.0 - self.phonetic_score


@dataclass
class SoundCorrespondence:
    """A recurring sound-correspondence pattern found across candidate pairs."""
    symbol_a: str | None              # None = gap (epenthesis / deletion)
    symbol_b: str | None
    position: str                     # "initial", "medial", "final"
    supporting_pairs: list[CandidatePair] = field(default_factory=list)
    weight: float = 0.0               # computed by Pass B


# ---------------------------------------------------------------------------
# Pass A — semantically-anchored phonetic alignment
# ---------------------------------------------------------------------------

def run_pass_a(
    corpus_a: Corpus,
    corpus_b: Corpus,
    gloss_threshold: float = GLOSS_MATCH_THRESHOLD,
) -> list[CandidatePair]:
    """Align word pairs whose glosses match across corpora.

    For every word in A, find all words in B whose gloss fuzzy-matches above
    the threshold, then run phonetic alignment on each matched pair.

    Returns candidates sorted by phonetic_score ascending (best first).
    """
    candidates: list[CandidatePair] = []

    for word_a in corpus_a.words:
        for word_b in corpus_b.words:
            similarity = fuzz.ratio(word_a.gloss.lower(), word_b.gloss.lower())
            if similarity < gloss_threshold:
                continue

            if not word_a.segments or not word_b.segments:
                continue

            result = align_pair(word_a.segments, word_b.segments)
            candidates.append(CandidatePair(
                word_a=word_a,
                word_b=word_b,
                gloss_similarity=similarity,
                alignment=result,
                phonetic_score=result.normalized_score,
            ))

    # Deduplicate: when the same gloss pair appears more than once (e.g. because
    # a word occurs in both a wordlist and a merged interlinear corpus), keep only
    # the candidate with the best phonetic score.
    best: dict[tuple[str, str], CandidatePair] = {}
    for c in candidates:
        key = (c.word_a.gloss.lower(), c.word_b.gloss.lower())
        if key not in best or c.phonetic_score < best[key].phonetic_score:
            best[key] = c
    candidates = list(best.values())

    candidates.sort(key=lambda c: c.phonetic_score)
    return candidates


# ---------------------------------------------------------------------------
# Pass B — systematicity detection + incremental re-scoring
# ---------------------------------------------------------------------------

def _column_position(col_index: int, total_cols: int) -> str:
    if total_cols == 1:
        return "initial"
    if col_index == 0:
        return "initial"
    if col_index == total_cols - 1:
        return "final"
    return "medial"


def _extract_column_pairs(
    candidates: list[CandidatePair],
) -> dict[tuple[str | None, str | None, str], list[CandidatePair]]:
    """Extract (symbol_a, symbol_b, position) -> [supporting pairs] mapping.

    Only non-rejected candidates contribute to correspondence patterns.
    """
    groups: dict[tuple[str | None, str | None, str], list[CandidatePair]] = {}

    for pair in candidates:
        if pair.status == "rejected":
            continue

        alignment = pair.alignment
        n = len(alignment.aligned_a)
        for col_idx, (pa, pb) in enumerate(
            zip(alignment.aligned_a, alignment.aligned_b)
        ):
            sym_a = pa.ipa_symbol if pa is not None else None
            sym_b = pb.ipa_symbol if pb is not None else None
            pos = _column_position(col_idx, n)
            key = (sym_a, sym_b, pos)
            if key not in groups:
                groups[key] = []
            if pair not in groups[key]:
                groups[key].append(pair)

    return groups


def _correspondence_weight(
    supporting_pairs: list[CandidatePair],
) -> float:
    """Compute a weight for a correspondence based on pair statuses.

    Accepted pairs contribute +2, pending +1, rejected −3.
    Result is normalised to [-1, 1] by dividing by the theoretical max.
    """
    score = sum(
        ACCEPTED_WEIGHT if p.status == "accepted"
        else (PENDING_WEIGHT if p.status == "pending" else REJECTED_WEIGHT)
        for p in supporting_pairs
    )
    n = len(supporting_pairs)
    if n == 0:
        return 0.0
    max_possible = n * ACCEPTED_WEIGHT
    return score / max_possible if max_possible > 0 else 0.0


def run_pass_b(
    candidates: list[CandidatePair],
    min_support: int = MIN_SUPPORT,
) -> tuple[list[SoundCorrespondence], list[CandidatePair]]:
    """Detect systematic sound correspondences and re-score candidates.

    Designed to rerun cheaply after every user accept/reject decision.
    Does NOT re-run alignment (Pass A); it only re-weights based on statuses.

    Args:
        candidates: The list from Pass A, with possibly updated statuses.
        min_support: Minimum number of pairs for a pattern to be "systematic."

    Returns:
        (correspondences, candidates) where candidates have updated
        systematicity_bonus and final_score.
    """
    column_groups = _extract_column_pairs(candidates)

    # Build systematic correspondences (those with enough support)
    correspondences: list[SoundCorrespondence] = []
    systematic: dict[tuple[str | None, str | None, str], SoundCorrespondence] = {}

    for key, supporting in column_groups.items():
        if len(supporting) < min_support:
            continue
        sym_a, sym_b, pos = key
        weight = _correspondence_weight(supporting)
        corr = SoundCorrespondence(
            symbol_a=sym_a,
            symbol_b=sym_b,
            position=pos,
            supporting_pairs=list(supporting),
            weight=weight,
        )
        correspondences.append(corr)
        systematic[key] = corr

    # Re-score each candidate based on how many of its columns are systematic
    for pair in candidates:
        if pair.status == "rejected":
            pair.systematicity_bonus = 0.0
            pair.final_score = 1.0 - pair.phonetic_score
            continue

        alignment = pair.alignment
        n = len(alignment.aligned_a)
        if n == 0:
            pair.systematicity_bonus = 0.0
            pair.final_score = 1.0 - pair.phonetic_score
            continue

        col_weights: list[float] = []
        for col_idx, (pa, pb) in enumerate(
            zip(alignment.aligned_a, alignment.aligned_b)
        ):
            sym_a = pa.ipa_symbol if pa is not None else None
            sym_b = pb.ipa_symbol if pb is not None else None
            pos = _column_position(col_idx, n)
            key = (sym_a, sym_b, pos)
            if key in systematic:
                col_weights.append(systematic[key].weight)
            else:
                # Non-systematic column: small penalty
                col_weights.append(-0.1)

        bonus = sum(col_weights) / len(col_weights) if col_weights else 0.0
        pair.systematicity_bonus = bonus

        # final_score: higher = more likely a real cognate
        phonetic_confidence = 1.0 - pair.phonetic_score  # flip: low distance = high conf
        pair.final_score = (
            PHONETIC_ALPHA * phonetic_confidence
            + SYSTEMATICITY_BETA * max(bonus, 0.0)
        )

    return correspondences, candidates


# ---------------------------------------------------------------------------
# Multi-language — run all pairs
# ---------------------------------------------------------------------------

def run_all_pairs(
    corpora: list[Corpus],
) -> dict[tuple[int, int], tuple[list[SoundCorrespondence], list[CandidatePair]]]:
    """Run Pass A + Pass B for every unique (i, j) pair in *corpora*.

    Returns a dict keyed by (i, j) with i < j, mapping to
    (correspondences, candidates) exactly as run_pass_b returns them.
    """
    results: dict[tuple[int, int], tuple[list, list]] = {}
    n = len(corpora)
    for i in range(n):
        for j in range(i + 1, n):
            cands = run_pass_a(corpora[i], corpora[j])
            corrs, cands = run_pass_b(cands)
            results[(i, j)] = (corrs, cands)
    return results
