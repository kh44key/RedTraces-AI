"""Extract normalized indicators of compromise from collected text."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from common.preprocessing import preprocess_text

HASH_PATTERN = re.compile(
    r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})(?![0-9a-fA-F])"
)
URL_PATTERN = re.compile(
    r"(?i)\b(?:https?|hxxps?)://[^\s<>\"']+"
)
DOMAIN_PATTERN = re.compile(
    r"(?i)(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z]{2,63}|onion)(?![\w.-])"
)
IPV4_CANDIDATE_PATTERN = re.compile(
    r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d)(?!\.\d)"
)
IPV6_CANDIDATE_PATTERN = re.compile(
    r"(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?![0-9a-fA-F:])"
)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"
FILE_SUFFIXES = {
    "apk",
    "bin",
    "dll",
    "dmg",
    "doc",
    "docx",
    "exe",
    "gif",
    "iso",
    "jpg",
    "js",
    "msi",
    "pdf",
    "png",
    "ps1",
    "rar",
    "sh",
    "tar",
    "txt",
    "xls",
    "xlsx",
    "zip",
}


def refang(value: str) -> str:
    """Backward-compatible wrapper around the Layer 3 preprocessor."""
    return preprocess_text(value).text


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def extract_iocs(text: str | None) -> dict[str, list[str]]:
    """Extract hashes, URLs, IP addresses, and domains from text."""
    normalized = preprocess_text(text).text
    indicators: dict[str, list[str]] = {
        "sha256": [],
        "sha1": [],
        "md5": [],
        "urls": [],
        "ipv4": [],
        "ipv6": [],
        "domains": [],
    }

    for candidate in HASH_PATTERN.findall(normalized):
        value = candidate.lower()
        key = {64: "sha256", 40: "sha1", 32: "md5"}[len(value)]
        indicators[key].append(value)

    for candidate in URL_PATTERN.findall(normalized):
        value = refang(candidate).rstrip(TRAILING_URL_PUNCTUATION)
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            indicators["urls"].append(value)
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                indicators["ipv4" if ip.version == 4 else "ipv6"].append(
                    ip.compressed
                )
            except ValueError:
                indicators["domains"].append(parsed.hostname.lower())

    for candidate in IPV4_CANDIDATE_PATTERN.findall(normalized):
        try:
            indicators["ipv4"].append(
                ipaddress.ip_address(candidate).compressed
            )
        except ValueError:
            continue

    for candidate in IPV6_CANDIDATE_PATTERN.findall(normalized):
        try:
            ip = ipaddress.ip_address(candidate)
            if ip.version == 6:
                indicators["ipv6"].append(ip.compressed)
        except ValueError:
            continue

    for candidate in DOMAIN_PATTERN.findall(normalized):
        domain = candidate.lower().rstrip(".")
        if domain.rsplit(".", 1)[-1] not in FILE_SUFFIXES:
            indicators["domains"].append(domain)

    return {key: _unique(values) for key, values in indicators.items()}


def enrich_metadata(metadata: dict[str, Any], text: str | None) -> dict[str, Any]:
    """Attach Layer 3 preprocessing and regex IOC extraction results."""
    preprocessing = preprocess_text(text)
    iocs = extract_iocs(preprocessing.text)
    return {
        **metadata,
        "preprocessing": preprocessing.metadata(),
        "iocs": iocs,
        "ioc_count": sum(len(values) for values in iocs.values()),
    }
