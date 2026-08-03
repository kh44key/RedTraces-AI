"""Generate validated STIX 2.1 bundles from normalized IOC records."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from stix2 import Bundle, Identity, Indicator, Relationship, parse
from stix2patterns.validator import run_validator

from common.ioc_normalizer import NormalizedIOC, normalize_record


DEFAULT_OUTPUT_DIRECTORY = Path("/output/stix_bundles")
HASH_PATTERN = re.compile(r"^[0-9a-fA-F]+$")
HASH_PROPERTIES = {
    "md5": ("MD5", 32),
    "sha1": ("SHA-1", 40),
    "sha256": ("SHA-256", 64),
}


def _stix_quote(value: str) -> str:
    """Escape a value for a STIX pattern single-quoted string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def indicator_pattern(record: NormalizedIOC | Mapping[str, Any]) -> str:
    """Build and validate the correct STIX pattern for an IOC type."""
    ioc = normalize_record(record)
    value = _stix_quote(ioc.value)
    if ioc.ioc_type == "ipv4":
        return f"[ipv4-addr:value = '{value}']"
    if ioc.ioc_type == "ipv6":
        return f"[ipv6-addr:value = '{value}']"
    if ioc.ioc_type == "domain":
        return f"[domain-name:value = '{value}']"
    if ioc.ioc_type == "url":
        return f"[url:value = '{value}']"
    if ioc.ioc_type in HASH_PROPERTIES:
        algorithm, expected_length = HASH_PROPERTIES[ioc.ioc_type]
        if len(ioc.value) != expected_length or not HASH_PATTERN.fullmatch(ioc.value):
            raise ValueError(f"Invalid {algorithm} hash: {ioc.value}")
        return f"[file:hashes.'{algorithm}' = '{value.lower()}']"
    raise ValueError(f"Unsupported IOC type: {ioc.ioc_type}")


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _source_name(record: NormalizedIOC) -> str:
    return f"RedTraces AI source: {record.platform}/{record.source}"


def build_stix_bundle(
    records: Iterable[NormalizedIOC | Mapping[str, Any]],
) -> Bundle:
    """Create one STIX bundle containing identities, indicators, and provenance links."""
    normalized = [normalize_record(record) for record in records]
    if not normalized:
        raise ValueError("At least one normalized IOC record is required")

    objects: list[Any] = []
    identities: dict[tuple[str, str], Identity] = {}
    seen: set[tuple[str, str, str, str]] = set()

    for record in normalized:
        source_key = (record.platform, record.source)
        identity = identities.get(source_key)
        if identity is None:
            identity = Identity(
                name=_source_name(record),
                identity_class="system",
                description=(
                    f"Content source observed by RedTraces AI on {record.platform}."
                ),
                custom_properties={
                    "x_redtraces_platform": record.platform,
                    "x_redtraces_source": record.source,
                    **(
                        {"x_redtraces_source_url": record.source_url}
                        if record.source_url
                        else {}
                    ),
                },
                allow_custom=True,
            )
            identities[source_key] = identity
            objects.append(identity)

        dedupe_key = (
            record.ioc_type,
            record.value.lower(),
            record.platform,
            record.source.lower(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        observed_at = _utc(record.collected_at)
        indicator = Indicator(
            name=f"{record.ioc_type.upper()} indicator: {record.value}",
            description=(
                f"Indicator collected from {record.platform} source {record.source}."
            ),
            pattern=indicator_pattern(record),
            pattern_type="stix",
            valid_from=observed_at,
            created_by_ref=identity.id,
            confidence=record.confidence,
            labels=["malicious-activity"],
            custom_properties={
                "x_redtraces_platform": record.platform,
                "x_redtraces_source": record.source,
                **(
                    {"x_redtraces_source_url": record.source_url}
                    if record.source_url
                    else {}
                ),
                **(
                    {"x_redtraces_message_id": record.message_id}
                    if record.message_id
                    else {}
                ),
            },
            allow_custom=True,
        )
        objects.append(indicator)
        objects.append(
            Relationship(
                relationship_type="indicates",
                source_ref=indicator.id,
                target_ref=identity.id,
                description="RedTraces AI provenance link to the observed source.",
                created_by_ref=identity.id,
            )
        )

    return Bundle(*objects, allow_custom=True)


def validate_bundle(bundle: Bundle) -> None:
    """Validate STIX objects and every Indicator pattern before persistence."""
    try:
        parsed = parse(bundle.serialize(), version="2.1", allow_custom=True)
    except Exception as error:
        raise ValueError(f"Invalid STIX 2.1 bundle: {error}") from error

    errors: list[str] = []
    for item in parsed.objects:
        if item.type == "indicator":
            errors.extend(run_validator(item.pattern, "2.1"))
    if errors:
        raise ValueError(f"Invalid STIX 2.1 bundle: {'; '.join(errors)}")


def save_stix_bundle(
    records: Iterable[NormalizedIOC | Mapping[str, Any]],
    *,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    timestamp: datetime | None = None,
) -> Path:
    """Build, validate, and atomically save one bundle for a collection run."""
    bundle = build_stix_bundle(records)
    validate_bundle(bundle)

    created_at = _utc(timestamp)
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / created_at.strftime("%Y%m%dT%H%M%S.%fZ.json")
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(json.loads(bundle.serialize()), indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
