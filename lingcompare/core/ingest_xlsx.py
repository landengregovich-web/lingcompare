"""Parse Excel workbooks (.xlsx / .xls / .ods) into Corpus objects.

Reads the first worksheet. Column detection (in priority order):
  1. Named columns: looks for a header row whose cells match known aliases
     for 'gloss' and 'IPA' (case-insensitive). A header row is any row where
     the second cell contains no IPA characters (uppercase or underscore).
  2. Positional fallback: first column = gloss, second column = IPA.

An optional third column (same aliases as morpheme_breakdown in wordlist CSV)
is treated as a morpheme breakdown string.
"""

from __future__ import annotations
import io

import openpyxl

from .ingest_wordlist import (
    ValidationError,
    _validate_and_tokenize_ipa,
    _parse_ipa_tokens,
    _parse_breakdown,
    _looks_like_header,
)
from .schema import Corpus, Word

_GLOSS_ALIASES = {"gloss", "word", "translation", "meaning", "english", "form", "entry"}
_IPA_ALIASES   = {"ipa", "ipa_form", "phonetic", "transcription", "pronunciation"}
_BD_ALIASES    = {"breakdown", "morpheme_breakdown", "morphemes", "segmentation"}


def _find_columns(header_row: list[str]) -> tuple[int | None, int | None, int | None]:
    """Return (gloss_col, ipa_col, breakdown_col) indices from a header row.

    Returns (None, None, None) if the row does not look like a header.
    """
    cells = [str(c).strip().lower() for c in header_row]
    gloss_col = ipa_col = bd_col = None
    for i, cell in enumerate(cells):
        if cell in _GLOSS_ALIASES:
            gloss_col = i
        elif cell in _IPA_ALIASES:
            ipa_col = i
        elif cell in _BD_ALIASES:
            bd_col = i
    return gloss_col, ipa_col, bd_col


def parse(
    file_bytes: bytes,
    language_name: str = "Unknown",
) -> tuple[Corpus, list[ValidationError]]:
    """Parse an Excel workbook from raw bytes.

    Args:
        file_bytes: Raw .xlsx / .xlsm / .ods file bytes.
        language_name: Assigned to the resulting Corpus.

    Returns:
        (corpus, errors) — errors is empty on full success.
    """
    errors: list[ValidationError] = []
    words: list[Word] = []

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        errors.append(ValidationError(
            row=0, column="file",
            message=f"Could not open workbook: {exc}",
        ))
        return Corpus(language_name=language_name), errors

    ws = wb.active
    all_rows = [
        [str(cell.value).strip() if cell.value is not None else "" for cell in row]
        for row in ws.iter_rows()
    ]
    wb.close()

    # Drop fully empty rows
    all_rows = [r for r in all_rows if any(c for c in r)]

    if not all_rows:
        return Corpus(language_name=language_name), errors

    # Header detection
    gloss_col = ipa_col = bd_col = None
    data_start = 0

    if len(all_rows) >= 2:
        first_row = all_rows[0]
        second_cell = first_row[1] if len(first_row) > 1 else ""
        # Detect header if second cell has uppercase/underscore OR matches a known alias
        is_header = _looks_like_header(second_cell) or (
            first_row[0].strip().lower() in _GLOSS_ALIASES or
            second_cell.strip().lower() in _IPA_ALIASES
        )
        if is_header:
            gloss_col, ipa_col, bd_col = _find_columns(first_row)
            data_start = 1

    # Positional fallback
    if gloss_col is None:
        gloss_col = 0
    if ipa_col is None:
        ipa_col = 1

    for line_num, row in enumerate(all_rows[data_start:], start=data_start + 1):
        if len(row) <= max(gloss_col, ipa_col):
            errors.append(ValidationError(
                row=line_num, column="IPA_form",
                message=f"Row has only {len(row)} column(s); need at least {max(gloss_col, ipa_col) + 1}.",
            ))
            continue

        gloss = row[gloss_col].strip()
        ipa_raw = row[ipa_col].strip()
        breakdown_raw = row[bd_col].strip() if bd_col is not None and bd_col < len(row) else ""

        if not gloss:
            errors.append(ValidationError(row=line_num, column="gloss", message="Gloss is empty."))
            continue
        if not ipa_raw:
            errors.append(ValidationError(row=line_num, column="IPA_form", message="IPA form is empty."))
            continue

        valid_tokens, tok_errors = _validate_and_tokenize_ipa(ipa_raw, line_num, "IPA_form")
        errors.extend(tok_errors)
        if tok_errors:
            continue

        if not valid_tokens:
            errors.append(ValidationError(
                row=line_num, column="IPA_form",
                message=f"No recognised IPA segments in {ipa_raw!r}.",
            ))
            continue

        segments, seg_errors = _parse_ipa_tokens(valid_tokens, line_num, "IPA_form")
        errors.extend(seg_errors)
        if seg_errors:
            continue

        morphemes = []
        if breakdown_raw:
            morphemes, bd_errors = _parse_breakdown(ipa_raw, breakdown_raw, line_num)
            errors.extend(bd_errors)
            if bd_errors:
                morphemes = []

        words.append(Word(gloss=gloss, segments=segments, morphemes=morphemes))

    return Corpus(language_name=language_name, words=words), errors
