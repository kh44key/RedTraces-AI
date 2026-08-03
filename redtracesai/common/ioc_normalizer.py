"""Convert grouped extractor output into canonical IOC records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping


TYPE_ALIASES = {
    "domain": "domain",
    "domains": "domain",
    "ipv4": "ipv4",
    "ipv4-addr": "ipv4",
    "ipv6": "ipv6",
    "ipv6-addr": "ipv6",
    "md5": "md5",
    "sha1": "sha1",
    "sha-1": "sha1",
    "sha256": "sha256",
    "sha-256": "sha256",
    "url": "url",
    "urls": "url",
}


@dataclass(frozen=True)
class NormalizedIOC:
    """One normalized IOC plus the provenance needed for STIX export."""

    ioc_type: str
    value: str
    platform: str
    source: str
    source_url: str | None = None
    collected_at: datetime | None = None
    message_id: str | None = None
    confidence: int = 50

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.collected_at is not None:
            result["collected_at"] = self.collected_at.isoformat()
        return result


def canonical_ioc_type(value: str) -> str:
    """Return the canonical IOC type accepted by downstream exporters."""
    key = value.strip().lower()
    try:
        return TYPE_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"Unsupported IOC type: {value}") from error


def normalize_record(record: NormalizedIOC | Mapping[str, Any]) -> NormalizedIOC:
    """Validate and normalize a dataclass or dictionary IOC record."""
    if isinstance(record, NormalizedIOC):
        values = record.as_dict()
    else:
        values = dict(record)

    collected_at = values.get("collected_at")
    if isinstance(collected_at, str):
        collected_at = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))

    confidence = int(values.get("confidence", 50))
    if not 0 <= confidence <= 100:
        raise ValueError("IOC confidence must be between 0 and 100")

    value = str(values.get("value", "")).strip()
    platform = str(values.get("platform", "")).strip().lower()
    source = str(values.get("source", "")).strip()
    if not value or not platform or not source:
        raise ValueError("IOC value, platform, and source are required")

    return NormalizedIOC(
        ioc_type=canonical_ioc_type(str(values.get("ioc_type", ""))),
        value=value,
        platform=platform,
        source=source,
        source_url=str(values["source_url"]).strip() if values.get("source_url") else None,
        collected_at=collected_at,
        message_id=str(values["message_id"]) if values.get("message_id") is not None else None,
        confidence=confidence,
    )


def normalize_ioc_groups(
    iocs: Mapping[str, Iterable[str]],
    *,
    platform: str,
    source: str,
    source_url: str | None = None,
    collected_at: datetime | None = None,
    message_id: str | int | None = None,
    confidence: int = 50,
) -> list[NormalizedIOC]:
    """Flatten the current ``metadata.iocs`` structure into IOC records."""
    records: list[NormalizedIOC] = []
    seen: set[tuple[str, str]] = set()
    for raw_type, values in iocs.items():
        ioc_type = canonical_ioc_type(raw_type)
        for raw_value in values:
            value = str(raw_value).strip()
            key = (ioc_type, value.lower())
            if not value or key in seen:
                continue
            seen.add(key)
            records.append(
                normalize_record(
                    {
                        "ioc_type": ioc_type,
                        "value": value,
                        "platform": platform,
                        "source": source,
                        "source_url": source_url,
                        "collected_at": collected_at,
                        "message_id": message_id,
                        "confidence": confidence,
                    }
                )
            )
    return records
