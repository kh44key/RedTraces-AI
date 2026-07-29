"""Layer 2 noise filtration, language detection, and content deduplication."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass

from langdetect import DetectorFactory, LangDetectException, detect
from sqlalchemy import select

from common.cti import env_flag
from common.db import AsyncSessionFactory
from common.ioc import extract_iocs
from common.models import CollectedMessage

DetectorFactory.seed = 0
WHITESPACE_PATTERN = re.compile(r"\s+")
REPEATED_CHARACTER_PATTERN = re.compile(r"(.)\1{11,}", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\b[\w@#.-]+\b", re.UNICODE)
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04ff]")
CHINESE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ARABIC_PATTERN = re.compile(r"[\u0600-\u06ff]")
PERSIAN_SPECIFIC_PATTERN = re.compile(r"[پچژگکی]")
LANGUAGE_ALIASES = {"zh-cn": "zh", "zh-tw": "zh"}


@dataclass(frozen=True)
class NoiseAnalysis:
    accepted: bool
    reason: str | None
    language: str
    normalized_sha256: str

    def metadata(self) -> dict[str, object]:
        return asdict(self)


def normalize_text(text: str | None) -> str:
    """Create a stable comparison form while preserving the stored raw text."""
    return WHITESPACE_PATTERN.sub(" ", (text or "").strip()).casefold()


def detect_language(text: str | None) -> str:
    """Return an ISO-like label for the languages in the project workflow."""
    normalized = normalize_text(text)
    if not normalized:
        return "unknown"
    if CHINESE_PATTERN.search(normalized):
        return "zh"
    if CYRILLIC_PATTERN.search(normalized):
        return "ru"
    if PERSIAN_SPECIFIC_PATTERN.search(normalized):
        return "fa"
    if ARABIC_PATTERN.search(normalized):
        return "ar"
    if len(normalized) < 20:
        return "unknown"
    try:
        detected = detect(normalized)
        return LANGUAGE_ALIASES.get(detected, detected)
    except LangDetectException:
        return "unknown"


def configured_languages() -> set[str]:
    return {
        value.strip().lower()
        for value in os.getenv(
            "NOISE_ALLOWED_LANGUAGES", "en,ru,zh,ar,fa,tr,unknown"
        ).split(",")
        if value.strip()
    }


def analyze_noise(
    text: str | None,
    *,
    has_attachments: bool = False,
) -> NoiseAnalysis:
    normalized = normalize_text(text)
    fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    language = detect_language(normalized)

    if not env_flag("NOISE_FILTER_ENABLED", True):
        return NoiseAnalysis(True, None, language, fingerprint)

    iocs = extract_iocs(normalized)
    has_iocs = any(iocs.values())
    minimum_length = max(int(os.getenv("NOISE_MIN_TEXT_LENGTH", "12")), 0)
    reason: str | None = None

    if not normalized and not has_attachments:
        reason = "empty"
    elif len(normalized) < minimum_length and not has_attachments and not has_iocs:
        reason = "low_signal"
    elif REPEATED_CHARACTER_PATTERN.search(normalized):
        reason = "repeated_characters"
    else:
        tokens = TOKEN_PATTERN.findall(normalized)
        if len(tokens) >= 8:
            most_common = max(tokens.count(token) for token in set(tokens))
            if most_common / len(tokens) >= 0.75:
                reason = "repeated_tokens"

    if reason is None and language not in configured_languages():
        reason = "unsupported_language"

    return NoiseAnalysis(reason is None, reason, language, fingerprint)


async def evaluate_message(
    platform: str,
    source: str,
    text: str | None,
    *,
    has_attachments: bool = False,
) -> NoiseAnalysis:
    """Analyze content and reject previously stored normalized duplicates."""
    analysis = analyze_noise(text, has_attachments=has_attachments)
    if (
        not analysis.accepted
        or not normalize_text(text)
        or not env_flag("NOISE_DEDUPLICATION_ENABLED", True)
    ):
        return analysis

    query = (
        select(CollectedMessage.id)
        .where(
            CollectedMessage.platform == platform,
            CollectedMessage.source == source,
            CollectedMessage.metadata_["noise"]["normalized_sha256"].as_string()
            == analysis.normalized_sha256,
        )
        .limit(1)
    )
    async with AsyncSessionFactory() as session:
        if await session.scalar(query) is not None:
            return NoiseAnalysis(
                False,
                "duplicate",
                analysis.language,
                analysis.normalized_sha256,
            )
    return analysis
