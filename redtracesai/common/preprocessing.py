"""Layer 3 text normalization and CTI defanging reversal."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass

PREPROCESSING_VERSION = "1.0"
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
INLINE_WHITESPACE_PATTERN = re.compile(r"[^\S\r\n]+")
EXCESS_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
DEFANGED_DOT_PATTERN = re.compile(
    r"(?<=[A-Za-z0-9])\s*"
    r"(?:\[\s*(?:\.|dot)\s*\]|\(\s*(?:\.|dot)\s*\)|\{\s*(?:\.|dot)\s*\})"
    r"\s*(?=[A-Za-z0-9])",
    re.IGNORECASE,
)
TEXTUAL_DOT_PATTERN = re.compile(
    r"(?<=[A-Za-z0-9])\s+dot\s+(?=[A-Za-z0-9])",
    re.IGNORECASE,
)
DEFANGED_SCHEME_SEPARATOR_PATTERN = re.compile(
    r"(?:\[\s*://\s*\]|\(\s*://\s*\)|\{\s*://\s*\})"
)
HXXPS_PATTERN = re.compile(r"\bhxxps(?=://)", re.IGNORECASE)
HXXP_PATTERN = re.compile(r"\bhxxp(?=://)", re.IGNORECASE)
MEOW_PATTERN = re.compile(r"\bmeow(?=://)", re.IGNORECASE)


@dataclass(frozen=True)
class PreprocessingResult:
    text: str
    transformations: tuple[str, ...]
    sha256: str

    def metadata(self) -> dict[str, object]:
        return {
            "version": PREPROCESSING_VERSION,
            "normalized_text": self.text,
            "transformations": list(self.transformations),
            "sha256": self.sha256,
        }


def _apply_pattern(
    value: str,
    pattern: re.Pattern[str],
    replacement: str,
    label: str,
    transformations: list[str],
) -> str:
    updated, count = pattern.subn(replacement, value)
    if count:
        transformations.append(label)
    return updated


def preprocess_text(text: str | None) -> PreprocessingResult:
    """Normalize text and reverse common CTI defanging deterministically."""
    value = text or ""
    transformations: list[str] = []

    decoded = html.unescape(value)
    if decoded != value:
        transformations.append("html_entities_decoded")
    value = decoded

    normalized = unicodedata.normalize("NFKC", value)
    if normalized != value:
        transformations.append("unicode_nfkc")
    value = normalized

    cleaned = ZERO_WIDTH_PATTERN.sub("", value)
    if cleaned != value:
        transformations.append("zero_width_removed")
    value = cleaned

    printable = "".join(
        character
        for character in value
        if character in {"\n", "\r", "\t"}
        or not unicodedata.category(character).startswith("C")
    )
    if printable != value:
        transformations.append("control_characters_removed")
    value = printable

    value = _apply_pattern(
        value,
        DEFANGED_SCHEME_SEPARATOR_PATTERN,
        "://",
        "scheme_separator_refanged",
        transformations,
    )
    value = _apply_pattern(
        value, HXXPS_PATTERN, "https", "hxxps_refanged", transformations
    )
    value = _apply_pattern(
        value, HXXP_PATTERN, "http", "hxxp_refanged", transformations
    )
    value = _apply_pattern(
        value, MEOW_PATTERN, "http", "meow_scheme_refanged", transformations
    )
    value = _apply_pattern(
        value, DEFANGED_DOT_PATTERN, ".", "bracketed_dot_refanged", transformations
    )
    value = _apply_pattern(
        value, TEXTUAL_DOT_PATTERN, ".", "textual_dot_refanged", transformations
    )

    compact = "\n".join(
        INLINE_WHITESPACE_PATTERN.sub(" ", line).strip()
        for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()
    compact = EXCESS_BLANK_LINES_PATTERN.sub("\n\n", compact)
    if compact != value:
        transformations.append("whitespace_normalized")
    value = compact

    return PreprocessingResult(
        text=value,
        transformations=tuple(dict.fromkeys(transformations)),
        sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
    )
