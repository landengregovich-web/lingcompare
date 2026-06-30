"""Phonetically-weighted sequence alignment.

Implements Needleman-Wunsch global alignment using PanPhon feature distances
as substitution costs, so phonetically similar pairs (p/b, t/d, s/z) cost less
than dissimilar pairs (p/n, k/a).

No LingPy dependency: PanPhon's Segment.norm_distance() provides the
feature-weighted substitution cost directly.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .schema import Phoneme, _ft

# ---------------------------------------------------------------------------
# Alignment cost constants
# ---------------------------------------------------------------------------

# Gap penalty: opening a gap (insertion/deletion).
# Calibrated so that a single-feature substitution (e.g. voiced/unvoiced pair)
# is cheaper than inserting a gap, but a maximally-distant substitution is not.
GAP_PENALTY: float = 0.6

# Maximum possible feature distance between any two segments (norm_distance
# returns values in [0, 1] since features are in {-1, 0, 1} and
# norm_distance divides by the number of features).  In practice PanPhon's
# norm_distance is bounded at 1.0.
MAX_FEATURE_DISTANCE: float = 1.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AlignmentResult:
    """Output of aligning two phoneme sequences."""
    aligned_a: list[Phoneme | None]      # None = gap in this sequence
    aligned_b: list[Phoneme | None]
    column_scores: list[float]           # per-column cost (0 = identical, higher = worse)
    raw_distance: float                  # sum of column costs
    normalized_score: float              # raw_distance / max_possible_distance
                                         # 0.0 = identical, 1.0 = maximally different


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------

def phoneme_distance(a: Phoneme, b: Phoneme) -> float:
    """Feature-weighted distance between two phonemes, in [0, 1].

    Uses PanPhon's norm_distance which divides the sum of absolute feature
    differences by the total number of features, giving a value in [0, 1].
    """
    seg_a = _ft.fts(a.ipa_symbol)
    seg_b = _ft.fts(b.ipa_symbol)
    if not seg_a or not seg_b:
        # Fallback: identity check only (shouldn't happen post-validation)
        return 0.0 if a.ipa_symbol == b.ipa_symbol else 1.0
    return seg_a.norm_distance(seg_b)


# ---------------------------------------------------------------------------
# Needleman-Wunsch alignment
# ---------------------------------------------------------------------------

def align_pair(
    seq_a: list[Phoneme],
    seq_b: list[Phoneme],
    gap_penalty: float = GAP_PENALTY,
) -> AlignmentResult:
    """Align two phoneme sequences using Needleman-Wunsch.

    Uses phonetically-weighted substitution costs (PanPhon feature distance)
    so that similar sounds (p/b) cost less to align than dissimilar ones (p/n).

    Args:
        seq_a: Phoneme sequence for language A.
        seq_b: Phoneme sequence for language B.
        gap_penalty: Cost of inserting a gap in either sequence.

    Returns:
        AlignmentResult with aligned columns and distance scores.
    """
    n, m = len(seq_a), len(seq_b)

    # Build score matrix (n+1) x (m+1)
    # score[i][j] = minimum cost to align seq_a[:i] with seq_b[:j]
    score = [[0.0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        score[i][0] = i * gap_penalty
    for j in range(1, m + 1):
        score[0][j] = j * gap_penalty

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_cost = phoneme_distance(seq_a[i - 1], seq_b[j - 1])
            score[i][j] = min(
                score[i - 1][j - 1] + sub_cost,   # substitution/match
                score[i - 1][j] + gap_penalty,     # gap in B
                score[i][j - 1] + gap_penalty,     # gap in A
            )

    raw_distance = score[n][m]

    # Traceback
    aligned_a: list[Phoneme | None] = []
    aligned_b: list[Phoneme | None] = []
    column_scores: list[float] = []

    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            sub_cost = phoneme_distance(seq_a[i - 1], seq_b[j - 1])
            if abs(score[i][j] - (score[i - 1][j - 1] + sub_cost)) < 1e-9:
                aligned_a.append(seq_a[i - 1])
                aligned_b.append(seq_b[j - 1])
                column_scores.append(sub_cost)
                i -= 1
                j -= 1
                continue
        if i > 0 and abs(score[i][j] - (score[i - 1][j] + gap_penalty)) < 1e-9:
            aligned_a.append(seq_a[i - 1])
            aligned_b.append(None)
            column_scores.append(gap_penalty)
            i -= 1
        else:
            aligned_a.append(None)
            aligned_b.append(seq_b[j - 1])
            column_scores.append(gap_penalty)
            j -= 1

    aligned_a.reverse()
    aligned_b.reverse()
    column_scores.reverse()

    # Normalise: divide by the worst case (all gaps, length = max of the two)
    max_possible = max(n, m) * gap_penalty if (n > 0 or m > 0) else 1.0
    normalized_score = raw_distance / max_possible if max_possible > 0 else 0.0

    return AlignmentResult(
        aligned_a=aligned_a,
        aligned_b=aligned_b,
        column_scores=column_scores,
        raw_distance=raw_distance,
        normalized_score=min(normalized_score, 1.0),
    )


def format_alignment(result: AlignmentResult) -> str:
    """Return a human-readable two-line alignment string.

    Example:
        f w e ɣ o
        f o ɡ - u
    """
    row_a = " ".join(p.ipa_symbol if p else "-" for p in result.aligned_a)
    row_b = " ".join(p.ipa_symbol if p else "-" for p in result.aligned_b)
    return f"{row_a}\n{row_b}"
