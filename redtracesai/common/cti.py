"""Shared cyber-threat-intelligence keyword configuration."""

from __future__ import annotations

import os
from collections.abc import Iterable

DEFAULT_CTI_KEYWORDS = (
    "ransomware,cve,zero-day,0day,exploit,botnet,stealer,infostealer,"
    "malware,data leak,breach,initial access,access broker,phishing"
)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def cti_keywords() -> tuple[str, ...]:
    raw = os.getenv("CTI_KEYWORDS", DEFAULT_CTI_KEYWORDS)
    return tuple(
        dict.fromkeys(keyword.strip().casefold() for keyword in raw.split(",") if keyword.strip())
    )


def matches_cti_keywords(
    values: Iterable[object], keywords: tuple[str, ...] | None = None
) -> bool:
    configured = keywords or cti_keywords()
    haystack = " ".join(str(value) for value in values if value is not None).casefold()
    return any(keyword in haystack for keyword in configured)
