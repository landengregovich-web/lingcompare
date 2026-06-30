"""Parse interlinear glossed text into Corpus objects.

Expected format — utterance blocks separated by blank lines.
Each block has three lines in this order:

    IPA:   aba-ta   kela
    GLOSS: water-PL big
    TRANS: the big waters   (optional)

Rules:
- IPA and GLOSS must have the same number of whitespace-separated words.
- Within each word, hyphens mark morpheme boundaries. The number of
  hyphen-separated pieces must match between IPA and GLOSS for that word.
- Gloss tags from GLOSS become the morpheme.gloss_tag on each Morpheme.
- The TRANS line (if present) becomes the Word's gloss; otherwise the
  concatenation of root gloss tags is used.
- The corpus-level gloss_glossary is populated from the user's own definitions
  passed in as a dict; it is never inferred from the data.

Validation errors are row-level and collected the same way as ingest_wordlist.
"""

from __future__ import annotations
import re
from dataclasses import dataclass

from .schema import Corpus, Morpheme, Phoneme, Word, tokenize_ipa, _ft
from .ingest_wordlist import ValidationError, _validate_and_tokenize_ipa, _parse_ipa_tokens


# Tag for each line type inside a block
_IPA_RE = re.compile(r"^IPA\s*:\s*(.+)$", re.IGNORECASE)
_GLOSS_RE = re.compile(r"^GLOSS\s*:\s*(.+)$", re.IGNORECASE)
_TRANS_RE = re.compile(r"^TRANS\s*:\s*(.*)$", re.IGNORECASE)


def _infer_position(morpheme_index: int, total: int) -> str:
    if total == 1:
        return "root"
    if morpheme_index == 0:
        return "prefix"
    if morpheme_index == total - 1:
        return "suffix"
    return "infix"


def _parse_block(
    block_lines: list[tuple[int, str]],  # (line_number, text) pairs
) -> tuple[list[Word], list[ValidationError]]:
    """Parse one utterance block into Word objects."""
    errors: list[ValidationError] = []
    words: list[Word] = []

    ipa_match = gloss_match = trans_match = None
    ipa_lineno = gloss_lineno = 0

    for lineno, line in block_lines:
        if m := _IPA_RE.match(line):
            ipa_match = m.group(1).strip()
            ipa_lineno = lineno
        elif m := _GLOSS_RE.match(line):
            gloss_match = m.group(1).strip()
            gloss_lineno = lineno
        elif m := _TRANS_RE.match(line):
            trans_match = m.group(1).strip()

    if ipa_match is None:
        errors.append(ValidationError(
            row=block_lines[0][0],
            column="IPA",
            message="Block is missing an IPA: line.",
        ))
        return words, errors

    if gloss_match is None:
        errors.append(ValidationError(
            row=block_lines[0][0],
            column="GLOSS",
            message="Block is missing a GLOSS: line.",
        ))
        return words, errors

    ipa_words = ipa_match.split()
    gloss_words = gloss_match.split()

    if len(ipa_words) != len(gloss_words):
        errors.append(ValidationError(
            row=ipa_lineno,
            column="IPA/GLOSS",
            message=(
                f"IPA has {len(ipa_words)} word(s) but GLOSS has {len(gloss_words)}. "
                "Each whitespace-separated token in IPA must align with one in GLOSS."
            ),
        ))
        return words, errors

    # Use TRANS words as glosses if provided and count matches; else fallback
    trans_words: list[str] | None = None
    if trans_match:
        tw = trans_match.split()
        trans_words = tw if len(tw) == len(ipa_words) else None

    for word_idx, (ipa_word, gloss_word) in enumerate(zip(ipa_words, gloss_words)):
        ipa_morphemes = ipa_word.split("-")
        gloss_morphemes = gloss_word.split("-")

        if len(ipa_morphemes) != len(gloss_morphemes):
            errors.append(ValidationError(
                row=ipa_lineno,
                column="IPA/GLOSS",
                message=(
                    f"Word #{word_idx + 1}: IPA {ipa_word!r} has {len(ipa_morphemes)} morpheme(s) "
                    f"but GLOSS {gloss_word!r} has {len(gloss_morphemes)}."
                ),
            ))
            continue

        all_segments: list[Phoneme] = []
        morpheme_objs: list[Morpheme] = []
        word_ok = True
        n_morphemes = len(ipa_morphemes)

        for morph_idx, (ipa_piece, gloss_tag) in enumerate(
            zip(ipa_morphemes, gloss_morphemes)
        ):
            valid_tokens, tok_errors = _validate_and_tokenize_ipa(
                ipa_piece, ipa_lineno, "IPA"
            )
            errors.extend(tok_errors)
            if tok_errors:
                word_ok = False
                continue

            phonemes, parse_errors = _parse_ipa_tokens(valid_tokens, ipa_lineno, "IPA")
            errors.extend(parse_errors)
            if parse_errors:
                word_ok = False
                continue

            position = _infer_position(morph_idx, n_morphemes)
            morpheme_objs.append(
                Morpheme(segments=phonemes, gloss_tag=gloss_tag, position=position)
            )
            all_segments.extend(phonemes)

        if not word_ok or not all_segments:
            continue

        # Determine word gloss.
        # TRANS is a free translation of the whole utterance — using its words
        # as individual word glosses only works reliably for single-word blocks
        # (e.g. a single entry "IPA: aɣwa / GLOSS: water-PL / TRANS: waters").
        # For multi-word utterances TRANS words are inflected English surface
        # forms ("eats", "cats") that differ from the GLOSS morpheme tags and
        # create near-duplicate candidates in Pass A.  We derive the gloss
        # from the GLOSS line instead:
        #   - multi-morpheme word: first morpheme tag is the stem (cat-PL → cat)
        #   - single-morpheme fused form: strip agreement after "." (eat.3SG → eat)
        # TRANS is still used verbatim for truly single-word blocks.
        if trans_words and len(ipa_words) == 1:
            word_gloss = trans_words[0]
        elif len(morpheme_objs) > 1:
            word_gloss = morpheme_objs[0].gloss_tag
        else:
            tag = morpheme_objs[0].gloss_tag if morpheme_objs else gloss_word
            word_gloss = tag.split(".")[0]

        words.append(Word(
            gloss=word_gloss,
            segments=all_segments,
            morphemes=morpheme_objs,
        ))

    return words, errors


def parse(
    content: str,
    language_name: str = "Unknown",
    gloss_glossary: dict[str, str] | None = None,
) -> tuple[Corpus, list[ValidationError]]:
    """Parse interlinear glossed text into a Corpus.

    Args:
        content: Raw interlinear text with IPA/GLOSS/TRANS blocks.
        language_name: Language name for the corpus.
        gloss_glossary: Optional user-provided {tag: meaning} dictionary.

    Returns:
        (corpus, errors) — errors non-empty on any validation failure.
    """
    all_errors: list[ValidationError] = []
    all_words: list[Word] = []

    # Split into blocks by blank lines
    lines = content.splitlines()
    blocks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append((lineno, stripped))
    if current:
        blocks.append(current)

    for block in blocks:
        words, errors = _parse_block(block)
        all_words.extend(words)
        all_errors.extend(errors)

    corpus = Corpus(
        language_name=language_name,
        words=all_words,
        gloss_glossary=gloss_glossary or {},
    )
    return corpus, all_errors
