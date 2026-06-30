"""Combination / scoring layer — full multi-factor evidence breakdown.

Produces a ScoredEvidence object for any CandidatePair, combining:
  - Phonetic alignment score         (Pass A)
  - Systematicity bonus/penalty      (Pass B)
  - Gloss-tag match support          (Grammar layer)
  - Sound-change typological plausibility (hardcoded naturalness table)
  - Inventory context                (does the target sound exist in B's inventory?)

Design intent
-------------
Pass B in cognate_engine.py already computes a fast final_score used for the
interactive feedback loop.  This module computes a *richer* breakdown — used
for the per-pair evidence panel in the UI — without replacing Pass B's scoring.
Both are kept: Pass B for cheap re-scoring, scoring.py for explainability.

Weights rationale
-----------------
phonetic (0.35) — primary phonological evidence; alignment distance is the
  most direct measure of sound similarity.
systematicity (0.35) — distinguishes real historical correspondences from
  accidental resemblances; equally weighted with phonetics because isolated
  look-alikes are the main failure mode of naive cognate detection.
gloss (0.15) — secondary; semantic anchoring is a prerequisite (it filtered
  Pass A candidates) rather than independent evidence.
typology (0.10) — supporting context; typological naturalness of the implied
  sound change adds plausibility but is not itself evidence of cognacy.
inventory (0.05) — weak constraint; a sound's absence from the target
  inventory slightly lowers confidence but is not disqualifying (borrowings
  and earlier strata can introduce sounds outside the productive inventory).
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .cognate_engine import CandidatePair, SoundCorrespondence
from .schema import Phoneme

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "phonetic": 0.35,
    "systematicity": 0.35,
    "gloss": 0.15,
    "typology": 0.10,
    "inventory": 0.05,
}

# ---------------------------------------------------------------------------
# Sound-change plausibility table
# ---------------------------------------------------------------------------
# Values in [0, 1]: 1.0 = cross-linguistically very common / natural,
# 0.0 = essentially unattested.  Tuples are (source_ipa, target_ipa).
# Based on well-documented typological generalizations (Bybee 2001,
# Hock 1991, Labov 1994).

_SOUND_CHANGE_PLAUSIBILITY: dict[tuple[str, str], float] = {
    # Identity — always plausible
    # (handled separately as 1.0 when symbols match)

    # Voicing alternations (very common)
    ("p", "b"): 0.80, ("b", "p"): 0.70,
    ("t", "d"): 0.80, ("d", "t"): 0.70,
    ("k", "g"): 0.80, ("g", "k"): 0.70,
    ("f", "v"): 0.75, ("v", "f"): 0.65,
    ("s", "z"): 0.75, ("z", "s"): 0.65,
    ("θ", "ð"): 0.80, ("ð", "θ"): 0.70,

    # Spirantization / lenition (very common in Romance, Germanic)
    ("p", "f"): 0.90, ("b", "v"): 0.85, ("b", "β"): 0.90,
    ("d", "ð"): 0.90, ("g", "ɣ"): 0.90, ("g", "j"): 0.70,
    ("k", "x"): 0.75, ("k", "h"): 0.65, ("k", "tʃ"): 0.60,
    ("f", "h"): 0.70, ("s", "h"): 0.65,

    # Place shifts (moderate)
    ("n", "m"): 0.60, ("m", "n"): 0.60,
    ("t", "s"): 0.70, ("s", "t"): 0.55,
    ("k", "tʃ"): 0.60, ("t", "tʃ"): 0.55,
    ("l", "r"): 0.65, ("r", "l"): 0.60,
    ("ɾ", "r"): 0.80, ("r", "ɾ"): 0.80,
    ("ɾ", "l"): 0.60, ("l", "ɾ"): 0.60,

    # Vowel shifts (moderate to common)
    ("a", "e"): 0.55, ("e", "a"): 0.50,
    ("a", "o"): 0.50, ("o", "a"): 0.45,
    ("e", "i"): 0.65, ("i", "e"): 0.60,
    ("o", "u"): 0.65, ("u", "o"): 0.60,
    ("e", "o"): 0.45, ("o", "e"): 0.45,

    # Deletion / epenthesis — handled via gap penalty in alignment,
    # but a gap aligned with a real segment is slightly penalized here
    (None, "ə"): 0.50, ("ə", None): 0.50,
}

_DEFAULT_PLAUSIBILITY: float = 0.30  # unknown change type


def sound_change_plausibility(sym_a: str | None, sym_b: str | None) -> float:
    """Return typological plausibility of the sound change sym_a → sym_b."""
    if sym_a is None or sym_b is None:
        return 0.50  # gap = epenthesis/deletion, moderately plausible
    if sym_a == sym_b:
        return 1.0
    return _SOUND_CHANGE_PLAUSIBILITY.get(
        (sym_a, sym_b),
        _SOUND_CHANGE_PLAUSIBILITY.get((sym_b, sym_a), _DEFAULT_PLAUSIBILITY),
    )


# ---------------------------------------------------------------------------
# Scored evidence
# ---------------------------------------------------------------------------

@dataclass
class ScoredEvidence:
    """Full multi-factor evidence breakdown for one CandidatePair."""
    pair: CandidatePair
    factor_scores: dict[str, float]   # factor name -> contribution in [0, 1]
    final_score: float                # weighted sum, [0, 1]
    narrative: str                    # human-readable explanation


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_scored_evidence(
    pair: CandidatePair,
    correspondences: list[SoundCorrespondence],
    inventory_b: set[Phoneme],
    gloss_support: float = 0.0,   # 0–1: fraction of morpheme tags confirmed
) -> ScoredEvidence:
    """Compute full multi-factor evidence for a candidate pair.

    Args:
        pair: The CandidatePair from Pass A/B.
        correspondences: Systematic correspondences from Pass B.
        inventory_b: Phoneme inventory of language B (for inventory check).
        gloss_support: Fraction of morpheme gloss tags in this pair that have
            confirmed cross-corpus tag correspondences (from Grammar page).
            0.0 if no morpheme data available.

    Returns:
        ScoredEvidence with per-factor scores and a narrative string.
    """
    factors: dict[str, float] = {}

    # ---- 1. Phonetic alignment ----
    phonetic_conf = 1.0 - pair.phonetic_score  # distance → confidence
    factors["phonetic"] = max(0.0, min(1.0, phonetic_conf))

    # ---- 2. Systematicity ----
    # Normalise the bonus (which can be negative) to [0, 1]
    sys_raw = pair.systematicity_bonus
    sys_norm = (sys_raw + 1.0) / 2.0  # map [-1,1] → [0,1]
    factors["systematicity"] = max(0.0, min(1.0, sys_norm))

    # ---- 3. Gloss (tag support) ----
    factors["gloss"] = max(0.0, min(1.0, gloss_support if gloss_support > 0 else
                           pair.gloss_similarity / 100.0))

    # ---- 4. Typological plausibility of implied sound changes ----
    alignment = pair.alignment
    plausibilities: list[float] = []
    for pa, pb in zip(alignment.aligned_a, alignment.aligned_b):
        sym_a = pa.ipa_symbol if pa is not None else None
        sym_b = pb.ipa_symbol if pb is not None else None
        plausibilities.append(sound_change_plausibility(sym_a, sym_b))
    typo_score = sum(plausibilities) / len(plausibilities) if plausibilities else 0.5
    factors["typology"] = typo_score

    # ---- 5. Inventory context ----
    # Does each phoneme in word_b's form appear in corpus B's inventory?
    b_syms = {p.ipa_symbol for p in inventory_b}
    b_word_syms = {p.ipa_symbol for p in pair.word_b.segments}
    if not b_syms or not b_word_syms:
        # No inventory data available — neutral
        inv_score = 0.5
    else:
        in_inv = sum(1 for s in b_word_syms if s in b_syms)
        inv_score = in_inv / len(b_word_syms)
    factors["inventory"] = inv_score

    # ---- Weighted combination ----
    final = sum(WEIGHTS[k] * factors[k] for k in WEIGHTS)

    # ---- Narrative ----
    narrative = _build_narrative(pair, factors, final)

    return ScoredEvidence(
        pair=pair,
        factor_scores=factors,
        final_score=final,
        narrative=narrative,
    )


def _build_narrative(
    pair: CandidatePair,
    factors: dict[str, float],
    final: float,
) -> str:
    """Build a human-readable summary of the evidence."""
    lines: list[str] = []

    pct = int(final * 100)
    lines.append(
        f"Overall confidence: {pct}% — "
        + ("strong candidate" if pct >= 70 else
           "moderate candidate" if pct >= 45 else
           "weak candidate")
        + "."
    )

    # Phonetic
    ph = factors["phonetic"]
    if ph >= 0.85:
        lines.append(f"Phonetically very similar (distance {pair.phonetic_score:.2f}).")
    elif ph >= 0.60:
        lines.append(f"Moderate phonetic similarity (distance {pair.phonetic_score:.2f}).")
    else:
        lines.append(f"Low phonetic similarity (distance {pair.phonetic_score:.2f}).")

    # Systematicity
    sb = pair.systematicity_bonus
    if sb > 0.2:
        lines.append("Alignment fits systematic cross-corpus sound correspondences (boosted).")
    elif sb < -0.1:
        lines.append("Alignment does not fit systematic patterns (penalised).")
    else:
        lines.append("Limited systematic pattern support.")

    # Typology
    ty = factors["typology"]
    if ty >= 0.75:
        lines.append("Implied sound changes are typologically common.")
    elif ty >= 0.50:
        lines.append("Implied sound changes are moderately attested cross-linguistically.")
    else:
        lines.append("Some implied sound changes are typologically unusual.")

    # Inventory
    inv = factors["inventory"]
    if inv < 0.80:
        lines.append(
            "One or more phonemes in the target word are not in the target inventory — "
            "possible borrowing or archaic stratum."
        )

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def score_all(
    candidates: list[CandidatePair],
    correspondences: list[SoundCorrespondence],
    inventory_b: set[Phoneme],
) -> list[ScoredEvidence]:
    """Compute ScoredEvidence for every candidate pair."""
    return [
        compute_scored_evidence(pair, correspondences, inventory_b)
        for pair in candidates
    ]
