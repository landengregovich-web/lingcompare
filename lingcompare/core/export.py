"""Export layer — serialise analysis results to CSV and JSON.

Three export targets:
  candidates_csv    — one row per word pair, flat, suitable for spreadsheets
  correspondences_csv — one row per systematic sound correspondence
  full_json         — structured dump of everything (lossless round-trip)
"""

from __future__ import annotations
import csv
import io
import json
from datetime import datetime, timezone

from .cognate_engine import CandidatePair, SoundCorrespondence
from .gloss_match import GlossTagMapping
from .phon_align import format_alignment
from .schema import Corpus
from .scoring import ScoredEvidence


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------

def candidates_csv(
    candidates: list[CandidatePair],
    lang_a: str = "A",
    lang_b: str = "B",
    scored: list[ScoredEvidence] | None = None,
) -> str:
    """Serialise candidate pairs to CSV.

    Columns:
      status, gloss_a, ipa_a, gloss_b, ipa_b,
      gloss_similarity, phonetic_score, systematicity_bonus,
      final_score (Pass B), [scored_final, phonetic_factor, systematicity_factor,
      gloss_factor, typology_factor, inventory_factor] (if scored provided),
      alignment_a, alignment_b
    """
    buf = io.StringIO()
    base_cols = [
        "status",
        f"gloss_{lang_a}", f"ipa_{lang_a}",
        f"gloss_{lang_b}", f"ipa_{lang_b}",
        "gloss_similarity",
        "phonetic_score",
        "systematicity_bonus",
        "final_score_pass_b",
    ]
    extra_cols = [
        "scored_final",
        "factor_phonetic", "factor_systematicity",
        "factor_gloss", "factor_typology", "factor_inventory",
    ] if scored else []
    align_cols = ["alignment_a", "alignment_b"]

    fieldnames = base_cols + extra_cols + align_cols
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    scored_map: dict[int, ScoredEvidence] = {}
    if scored:
        scored_map = {id(ev.pair): ev for ev in scored}

    for pair in candidates:
        align_lines = format_alignment(pair.alignment).split("\n")
        row: dict = {
            "status": pair.status,
            f"gloss_{lang_a}": pair.word_a.gloss,
            f"ipa_{lang_a}": pair.word_a.ipa,
            f"gloss_{lang_b}": pair.word_b.gloss,
            f"ipa_{lang_b}": pair.word_b.ipa,
            "gloss_similarity": f"{pair.gloss_similarity:.1f}",
            "phonetic_score": f"{pair.phonetic_score:.4f}",
            "systematicity_bonus": f"{pair.systematicity_bonus:+.4f}",
            "final_score_pass_b": f"{pair.final_score:.4f}",
            "alignment_a": align_lines[0] if align_lines else "",
            "alignment_b": align_lines[1] if len(align_lines) > 1 else "",
        }
        ev = scored_map.get(id(pair))
        if scored and ev:
            row["scored_final"] = f"{ev.final_score:.4f}"
            for factor in ("phonetic", "systematicity", "gloss", "typology", "inventory"):
                row[f"factor_{factor}"] = f"{ev.factor_scores.get(factor, 0.0):.4f}"
        writer.writerow(row)

    return buf.getvalue()


def correspondences_csv(correspondences: list[SoundCorrespondence]) -> str:
    """Serialise systematic correspondences to CSV."""
    buf = io.StringIO()
    fieldnames = ["symbol_a", "symbol_b", "position", "weight", "support_count"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for corr in sorted(correspondences, key=lambda c: -c.weight):
        writer.writerow({
            "symbol_a": corr.symbol_a,
            "symbol_b": corr.symbol_b,
            "position": corr.position,
            "weight": f"{corr.weight:.4f}",
            "support_count": len(corr.supporting_pairs),
        })
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def full_json(
    corpus_a: Corpus,
    corpus_b: Corpus,
    candidates: list[CandidatePair],
    correspondences: list[SoundCorrespondence],
    tag_mappings: list[GlossTagMapping] | None = None,
    scored: list[ScoredEvidence] | None = None,
) -> str:
    """Serialise the full analysis to JSON.

    Structure:
      {
        "meta": { "lang_a", "lang_b", "exported_at" },
        "phoneme_inventories": { "lang_a": [...], "lang_b": [...] },
        "candidates": [ { ... } ],
        "correspondences": [ { ... } ],
        "tag_mappings": [ { ... } ]  # omitted if None
      }
    """
    scored_map: dict[int, ScoredEvidence] = {}
    if scored:
        scored_map = {id(ev.pair): ev for ev in scored}

    doc: dict = {
        "meta": {
            "lang_a": corpus_a.language_name,
            "lang_b": corpus_b.language_name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "phoneme_inventories": {
            corpus_a.language_name: sorted(
                p.ipa_symbol for p in corpus_a.phoneme_inventory
            ),
            corpus_b.language_name: sorted(
                p.ipa_symbol for p in corpus_b.phoneme_inventory
            ),
        },
        "candidates": [_pair_to_dict(p, scored_map) for p in candidates],
        "correspondences": [_corr_to_dict(c) for c in correspondences],
    }

    if tag_mappings is not None:
        doc["tag_mappings"] = [_tag_to_dict(t) for t in tag_mappings]

    return json.dumps(doc, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _pair_to_dict(pair: CandidatePair, scored_map: dict) -> dict:
    align_lines = format_alignment(pair.alignment).split("\n")
    d: dict = {
        "status": pair.status,
        "gloss_a": pair.word_a.gloss,
        "ipa_a": pair.word_a.ipa,
        "gloss_b": pair.word_b.gloss,
        "ipa_b": pair.word_b.ipa,
        "gloss_similarity": round(pair.gloss_similarity, 2),
        "phonetic_score": round(pair.phonetic_score, 6),
        "systematicity_bonus": round(pair.systematicity_bonus, 6),
        "final_score_pass_b": round(pair.final_score, 6),
        "alignment": {
            "a": align_lines[0] if align_lines else "",
            "b": align_lines[1] if len(align_lines) > 1 else "",
        },
    }
    ev = scored_map.get(id(pair))
    if ev:
        d["scored"] = {
            "final": round(ev.final_score, 6),
            "factors": {k: round(v, 6) for k, v in ev.factor_scores.items()},
            "narrative": ev.narrative,
        }
    return d


def _corr_to_dict(corr: SoundCorrespondence) -> dict:
    return {
        "symbol_a": corr.symbol_a,
        "symbol_b": corr.symbol_b,
        "position": corr.position,
        "weight": round(corr.weight, 6),
        "support_count": len(corr.supporting_pairs),
    }


def _tag_to_dict(tag: GlossTagMapping) -> dict:
    return {
        "tag_a": tag.tag_a,
        "tag_b": tag.tag_b,
        "tag_similarity": round(tag.tag_similarity, 2),
        "def_similarity": round(tag.def_similarity, 2),
        "combined_score": round(tag.combined_score, 2),
        "status": tag.status,
    }
