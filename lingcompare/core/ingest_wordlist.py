"""Parse wordlist CSV files into Corpus objects.

Expected CSV format (header row optional):
    gloss, IPA_form[, morpheme_breakdown]

morpheme_breakdown (optional): morpheme-segmented IPA using hyphens, e.g. "aba-ta".
The non-hyphen characters in the breakdown must match the IPA_form characters exactly.

Validation errors are collected alongside any partial corpus; callers should
treat a non-empty errors list as a hard failure.
"""

from __future__ import annotations
import csv
import io
from dataclasses import dataclass

from .schema import Corpus, Morpheme, Phoneme, Word, tokenize_ipa, _ft


@dataclass
class ValidationError:
    row: int
    column: str
    message: str

    def __str__(self) -> str:
        return f"Row {self.row}, column '{self.column}': {self.message}"


def _validate_and_tokenize_ipa(
    ipa_raw: str, row: int, column: str
) -> tuple[list[str], list[ValidationError]]:
    """Tokenize an IPA string and surface any unrecognized characters as errors.

    Uses segs_safe() which includes unrecognized characters as single-char tokens,
    then checks each token with fts(). Unknown tokens become ValidationErrors.
    """
    errors: list[ValidationError] = []
    all_tokens = _ft.segs_safe(ipa_raw)  # includes invalid chars as single-char tokens
    valid_tokens: list[str] = []
    for token in all_tokens:
        if _ft.fts(token):
            valid_tokens.append(token)
        else:
            codepoints = " ".join(f"U+{ord(c):04X}" for c in token)
            errors.append(ValidationError(
                row=row,
                column=column,
                message=(
                    f"Unknown IPA character {token!r} ({codepoints}) in {ipa_raw!r}. "
                    "Check that the character is a valid IPA segment."
                ),
            ))
    return valid_tokens, errors


def _parse_ipa_tokens(
    tokens: list[str], row: int, column: str
) -> tuple[list[Phoneme], list[ValidationError]]:
    """Convert pre-validated IPA token strings to Phoneme objects."""
    phonemes: list[Phoneme] = []
    errors: list[ValidationError] = []
    for token in tokens:
        try:
            phonemes.append(Phoneme.from_ipa(token))
        except ValueError as exc:
            errors.append(ValidationError(row=row, column=column, message=str(exc)))
    return phonemes, errors


def _parse_breakdown(
    ipa_form: str,
    breakdown: str,
    row: int,
) -> tuple[list[Morpheme], list[ValidationError]]:
    """Split an IPA form into morphemes using a hyphen-delimited breakdown string.

    The breakdown string must have the same non-hyphen characters as the IPA form.
    Each hyphen-delimited piece is one morpheme.  Gloss tags default to the piece
    itself; users refine them in the UI glossary.
    """
    errors: list[ValidationError] = []
    morphemes: list[Morpheme] = []

    breakdown_stripped = breakdown.replace("-", "")
    ipa_stripped = ipa_form.replace("-", "")
    if breakdown_stripped != ipa_stripped:
        errors.append(ValidationError(
            row=row,
            column="morpheme_breakdown",
            message=(
                f"Breakdown {breakdown!r} characters ({breakdown_stripped!r}) "
                f"do not match IPA form characters ({ipa_stripped!r}) after removing hyphens."
            ),
        ))
        return morphemes, errors

    pieces = breakdown.split("-")
    n = len(pieces)
    for i, piece in enumerate(pieces):
        valid_tokens, errs = _validate_and_tokenize_ipa(piece, row, "morpheme_breakdown")
        errors.extend(errs)
        phonemes, parse_errs = _parse_ipa_tokens(valid_tokens, row, "morpheme_breakdown")
        errors.extend(parse_errs)
        if i == 0 and n > 1:
            position = "prefix"
        elif i == n - 1 and n > 1:
            position = "suffix"
        else:
            position = "root"
        morphemes.append(Morpheme(segments=phonemes, gloss_tag=piece, position=position))

    return morphemes, errors


def _looks_like_header(cell: str) -> bool:
    """Return True if a cell looks like a column header rather than an IPA form.

    Valid IPA forms never contain uppercase letters or underscores.
    Header labels like 'IPA_form', 'Word', 'Gloss' always contain one of these.
    """
    return any(c.isupper() or c == "_" for c in cell)


def parse(
    content: str,
    language_name: str = "Unknown",
    has_header: bool | None = None,
) -> tuple[Corpus, list[ValidationError]]:
    """Parse a wordlist CSV string into a Corpus.

    Args:
        content: Raw CSV text.
        language_name: Name to assign to the corpus.
        has_header: If None, auto-detect by checking the second cell of the
                    first row for uppercase letters or underscores (IPA has neither).

    Returns:
        (corpus, errors) — errors is empty on full success.
        On partial failure, corpus.words contains only the rows that parsed cleanly.
    """
    errors: list[ValidationError] = []
    words: list[Word] = []

    reader = csv.reader(io.StringIO(content.strip()))
    rows = list(reader)
    if not rows:
        return Corpus(language_name=language_name), errors

    if has_header is None:
        if len(rows) < 2:
            # Can't reliably tell header from data with a single row — assume data.
            has_header = False
        else:
            first_ipa_candidate = rows[0][1].strip() if len(rows[0]) > 1 else ""
            has_header = _looks_like_header(first_ipa_candidate)

    data_rows = rows[1:] if has_header else rows

    for line_num, row in enumerate(data_rows, start=2 if has_header else 1):
        if not row or all(cell.strip() == "" for cell in row):
            continue

        if len(row) < 2:
            errors.append(ValidationError(
                row=line_num,
                column="IPA_form",
                message="Row must have at least two columns (gloss, IPA_form).",
            ))
            continue

        gloss = row[0].strip()
        ipa_raw = row[1].strip()
        breakdown_raw = row[2].strip() if len(row) > 2 else ""

        if not gloss:
            errors.append(ValidationError(
                row=line_num, column="gloss", message="Gloss is empty."
            ))
            continue
        if not ipa_raw:
            errors.append(ValidationError(
                row=line_num, column="IPA_form", message="IPA form is empty."
            ))
            continue

        valid_tokens, tok_errors = _validate_and_tokenize_ipa(ipa_raw, line_num, "IPA_form")
        errors.extend(tok_errors)
        if tok_errors:
            continue

        if not valid_tokens:
            errors.append(ValidationError(
                row=line_num,
                column="IPA_form",
                message=f"Could not tokenize IPA form {ipa_raw!r} — no recognized IPA segments found.",
            ))
            continue

        segments, seg_errors = _parse_ipa_tokens(valid_tokens, line_num, "IPA_form")
        errors.extend(seg_errors)
        if seg_errors:
            continue

        if breakdown_raw:
            morphemes, bd_errors = _parse_breakdown(ipa_raw, breakdown_raw, line_num)
            errors.extend(bd_errors)
            if bd_errors:
                morphemes = []
        else:
            morphemes = []

        words.append(Word(gloss=gloss, segments=segments, morphemes=morphemes))

    return Corpus(language_name=language_name, words=words), errors
