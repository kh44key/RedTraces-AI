"""Layer 2 noise filtering: language, spam, exact and near-duplicate checks."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import redis.asyncio as redis
try:
    import fasttext
except ImportError:  # Optional local model support.
    fasttext = None
try:
    import joblib
except ImportError:  # Optional local spam-classifier support.
    joblib = None
try:
    from datasketch import MinHash, MinHashLSH
except ImportError:  # Exact database/Redis deduplication remains available.
    MinHash = MinHashLSH = None
try:
    from langdetect import DetectorFactory, LangDetectException, detect
except ImportError:  # Unicode heuristics below remain available.
    DetectorFactory = None
    LangDetectException = Exception
    detect = None
from sqlalchemy import select

from common.cti import env_flag
from common.db import AsyncSessionFactory
from common.ioc import extract_iocs
from common.models import CollectedMessage

if DetectorFactory is not None:
    DetectorFactory.seed = 0
WHITESPACE_PATTERN = re.compile(r"\s+")
REPEATED_CHARACTER_PATTERN = re.compile(r"(.)\1{11,}", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\b[\w@#.-]+\b", re.UNICODE)
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04ff]")
CHINESE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ARABIC_PATTERN = re.compile(r"[\u0600-\u06ff]")
PERSIAN_SPECIFIC_PATTERN = re.compile(r"[Ù¾Ú†Ú˜Ú¯Ú©ÛŒ]")
LANGUAGE_ALIASES = {"zh-cn": "zh", "zh-tw": "zh", "fa-ir": "fa"}
# This assignment intentionally follows the legacy pattern above so Persian
# detection remains correct even if that source file was opened with a legacy
# Windows code page at some point.
PERSIAN_SPECIFIC_PATTERN = re.compile(r"[\u067e\u0686\u0698\u06af\u06a9\u06cc]")

_fasttext_model: Any | None = None
_fasttext_model_path: str | None = None
_spam_classifier: Any | None = None
_spam_classifier_path: str | None = None
_redis_client: redis.Redis | None = None
_redis_url: str | None = None
_near_indexes: dict[str, MinHashLSH] = {}
_near_index_keys: dict[str, deque[str]] = {}


@dataclass(frozen=True)
class NoiseAnalysis:
    accepted: bool
    reason: str | None
    language: str
    normalized_sha256: str
    language_detector: str = "heuristic_langdetect"
    language_confidence: float | None = None
    spam_probability: float | None = None

    def metadata(self) -> dict[str, object]:
        return asdict(self)


def normalize_text(text: str | None) -> str:
    """Create a stable comparison form while preserving the stored raw text."""
    return WHITESPACE_PATTERN.sub(" ", (text or "").strip()).casefold()


def _load_fasttext_model() -> Any | None:
    global _fasttext_model, _fasttext_model_path
    path = os.getenv("NOISE_FASTTEXT_MODEL_PATH", "").strip()
    if fasttext is None or not path or not Path(path).is_file():
        return None
    if _fasttext_model is None or _fasttext_model_path != path:
        _fasttext_model = fasttext.load_model(path)
        _fasttext_model_path = path
    return _fasttext_model


def detect_language_details(text: str | None) -> tuple[str, str, float | None]:
    """Prefer local FastText lid.176, with the prior detector as a safe fallback."""
    normalized = normalize_text(text)
    if not normalized:
        return "unknown", "empty", None

    try:
        model = _load_fasttext_model()
        if model is not None:
            clean_text = normalized.replace("\n", " ")
            # fasttext-wheel 0.9.2 calls ``np.array(..., copy=False)`` in its
            # public wrapper, which breaks under NumPy 2.x. The underlying
            # binding returns the same label/probability tuple directly.
            if hasattr(model, "f"):
                probability, raw_label = model.f.predict(clean_text, 1, 0.0, "strict")[0]
            else:
                labels, probabilities = model.predict(clean_text, k=1)
                raw_label, probability = labels[0], probabilities[0]
            label = str(raw_label).removeprefix("__label__").lower()
            return LANGUAGE_ALIASES.get(label, label), "fasttext_lid176", float(probability)
    except Exception:
        # Language detection must never stop collection. The fallback below keeps
        # operating if a local model file is corrupt or incompatible.
        pass

    if CHINESE_PATTERN.search(normalized):
        return "zh", "heuristic", None
    if CYRILLIC_PATTERN.search(normalized):
        return "ru", "heuristic", None
    if PERSIAN_SPECIFIC_PATTERN.search(normalized):
        return "fa", "heuristic", None
    if ARABIC_PATTERN.search(normalized):
        return "ar", "heuristic", None
    if len(normalized) < 20:
        return "unknown", "heuristic", None
    try:
        if detect is None:
            return "unknown", "heuristic", None
        detected = detect(normalized)
        return LANGUAGE_ALIASES.get(detected, detected), "langdetect", None
    except LangDetectException:
        return "unknown", "langdetect", None


def detect_language(text: str | None) -> str:
    """Backward-compatible language label used by existing callers and tests."""
    return detect_language_details(text)[0]


def configured_languages() -> set[str]:
    return {
        value.strip().lower()
        for value in os.getenv(
            "NOISE_ALLOWED_LANGUAGES", "en,ru,zh,ar,fa,tr,unknown"
        ).split(",")
        if value.strip()
    }


def _load_spam_classifier() -> Any | None:
    global _spam_classifier, _spam_classifier_path
    if joblib is None or not env_flag("NOISE_SPAM_CLASSIFIER_ENABLED", True):
        return None
    path = os.getenv("NOISE_SPAM_MODEL_PATH", "").strip()
    if not path or not Path(path).is_file():
        return None
    if _spam_classifier is None or _spam_classifier_path != path:
        _spam_classifier = joblib.load(path)
        _spam_classifier_path = path
    return _spam_classifier


def spam_probability(text: str) -> float | None:
    """Return the locally trained classifier's spam probability, if available."""
    try:
        classifier = _load_spam_classifier()
        if classifier is None:
            return None
        probabilities = classifier.predict_proba([text])[0]
        classes = list(classifier.classes_)
        spam_index = classes.index(1) if 1 in classes else classes.index("spam")
        return float(probabilities[spam_index])
    except Exception:
        return None


def analyze_noise(
    text: str | None,
    *,
    has_attachments: bool = False,
) -> NoiseAnalysis:
    normalized = normalize_text(text)
    fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    language, detector, language_confidence = detect_language_details(normalized)

    if not env_flag("NOISE_FILTER_ENABLED", True):
        return NoiseAnalysis(
            True, None, language, fingerprint, detector, language_confidence
        )

    iocs = extract_iocs(normalized)
    has_iocs = any(iocs.values())
    minimum_length = max(int(os.getenv("NOISE_MIN_TEXT_LENGTH", "12")), 0)
    reason: str | None = None
    probability: float | None = None

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

    if reason is None and normalized:
        probability = spam_probability(normalized)
        threshold = float(os.getenv("NOISE_SPAM_THRESHOLD", "0.80"))
        if probability is not None and probability >= threshold:
            reason = "spam_classifier"

    return NoiseAnalysis(
        reason is None,
        reason,
        language,
        fingerprint,
        detector,
        language_confidence,
        probability,
    )


async def _cache_client() -> redis.Redis | None:
    global _redis_client, _redis_url
    if not env_flag("NOISE_CACHE_ENABLED", True):
        return None
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    if _redis_client is None or _redis_url != url:
        _redis_client = redis.from_url(url, decode_responses=True)
        _redis_url = url
    try:
        await _redis_client.ping()
        return _redis_client
    except redis.RedisError:
        return None


def _cache_key(platform: str, source: str, fingerprint: str) -> str:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"redtraces:noise:{platform}:{source_hash}:{fingerprint}"


async def _cached_duplicate(platform: str, source: str, fingerprint: str) -> bool:
    client = await _cache_client()
    if client is None:
        return False
    try:
        return await client.exists(_cache_key(platform, source, fingerprint)) > 0
    except redis.RedisError:
        return False


async def _remember_cached_message(platform: str, source: str, fingerprint: str) -> None:
    client = await _cache_client()
    if client is None:
        return
    ttl = max(int(os.getenv("NOISE_CACHE_TTL_SECONDS", "86400")), 1)
    try:
        await client.set(_cache_key(platform, source, fingerprint), "1", ex=ttl)
    except redis.RedisError:
        return


async def _record_layer2_result(analysis: NoiseAnalysis) -> None:
    """Keep lightweight live counters for the dashboard in Redis."""
    client = await _cache_client()
    if client is None:
        return
    fields = {
        "processed": 1,
        "accepted" if analysis.accepted else "rejected": 1,
        f"language:{analysis.language}": 1,
        f"detector:{analysis.language_detector}": 1,
    }
    if analysis.reason:
        fields[f"reason:{analysis.reason}"] = 1
    try:
        await client.hincrby("redtraces:layer2:metrics", "processed", 1)
        for field, amount in fields.items():
            if field != "processed":
                await client.hincrby("redtraces:layer2:metrics", field, amount)
    except redis.RedisError:
        return


def _minhash(text: str) -> MinHash:
    permutations = max(int(os.getenv("NOISE_NEAR_DUPLICATE_PERMUTATIONS", "128")), 32)
    sketch = MinHash(num_perm=permutations)
    tokens = TOKEN_PATTERN.findall(text)
    shingles = {
        " ".join(tokens[index : index + 3])
        for index in range(max(len(tokens) - 2, 1))
    }
    for shingle in shingles or {text}:
        sketch.update(shingle.encode("utf-8"))
    return sketch


def _near_duplicate(platform: str, source: str, fingerprint: str, text: str) -> bool:
    """Query/update a per-source MinHash LSH index held by this collector process."""
    if MinHash is None or MinHashLSH is None or not env_flag("NOISE_NEAR_DUPLICATE_ENABLED", True) or not text:
        return False
    threshold = float(os.getenv("NOISE_NEAR_DUPLICATE_THRESHOLD", "0.85"))
    threshold = min(max(threshold, 0.1), 0.99)
    index_key = f"{platform}:{source}"
    index = _near_indexes.get(index_key)
    if index is None:
        index = MinHashLSH(
            threshold=threshold,
            num_perm=max(int(os.getenv("NOISE_NEAR_DUPLICATE_PERMUTATIONS", "128")), 32),
        )
        _near_indexes[index_key] = index
        _near_index_keys[index_key] = deque()
    sketch = _minhash(text)
    if index.query(sketch):
        return True
    index.insert(fingerprint, sketch)
    keys = _near_index_keys[index_key]
    keys.append(fingerprint)
    maximum_entries = max(int(os.getenv("NOISE_NEAR_DUPLICATE_MAX_ENTRIES", "10000")), 1)
    if len(keys) > maximum_entries:
        index.remove(keys.popleft())
    return False


async def evaluate_message(
    platform: str,
    source: str,
    text: str | None,
    *,
    has_attachments: bool = False,
) -> NoiseAnalysis:
    """Apply Layer 2 checks and reject exact or near-duplicate source content."""
    analysis = analyze_noise(text, has_attachments=has_attachments)
    if (
        not analysis.accepted
        or not normalize_text(text)
        or not env_flag("NOISE_DEDUPLICATION_ENABLED", True)
    ):
        await _record_layer2_result(analysis)
        return analysis

    if await _cached_duplicate(platform, source, analysis.normalized_sha256):
        result = NoiseAnalysis(
            False, "duplicate_cache", analysis.language, analysis.normalized_sha256,
            analysis.language_detector, analysis.language_confidence, analysis.spam_probability,
        )
        await _record_layer2_result(result)
        return result
    if _near_duplicate(platform, source, analysis.normalized_sha256, normalize_text(text)):
        result = NoiseAnalysis(
            False, "near_duplicate", analysis.language, analysis.normalized_sha256,
            analysis.language_detector, analysis.language_confidence, analysis.spam_probability,
        )
        await _record_layer2_result(result)
        return result

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
            result = NoiseAnalysis(
                False, "duplicate", analysis.language, analysis.normalized_sha256,
                analysis.language_detector, analysis.language_confidence, analysis.spam_probability,
            )
            await _record_layer2_result(result)
            return result
    await _remember_cached_message(platform, source, analysis.normalized_sha256)
    await _record_layer2_result(analysis)
    return analysis
