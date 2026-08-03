"""Generate batched Sigma YAML rules from network IOCs in the STIX store."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml

from common.stix_store import DEFAULT_DATABASE_PATH, indicator_value_and_type


DEFAULT_OUTPUT_DIRECTORY = Path("/output/sigma_rules")
RULE_NAMESPACE = uuid.UUID("37686ed6-8232-4b1d-8af8-e19e417425a9")
HIGH_CONFIDENCE_THRESHOLD = 75
RULE_CONFIG = {
    "ip": {
        "title": "RedTraces AI - Observed Malicious Destination IPs",
        "description": "Detects network traffic to IP indicators collected by RedTraces AI.",
        "category": "firewall",
        "field": "destination.ip",
    },
    "domain": {
        "title": "RedTraces AI - Observed Malicious DNS Queries",
        "description": "Detects DNS queries for domain indicators collected by RedTraces AI.",
        "category": "dns",
        "field": "dns.query.name",
    },
    "url": {
        "title": "RedTraces AI - Observed Malicious URL Domains",
        "description": "Detects proxy traffic to URL domains collected by RedTraces AI.",
        "category": "proxy",
        "field": "url.domain",
    },
}


@dataclass
class IOCBatch:
    values: set[str] = field(default_factory=set)
    confidence: int | None = None
    tags: set[str] = field(default_factory=set)


def _rule_type(ioc_type: str) -> str | None:
    if ioc_type in {"ipv4", "ipv6", "ip"}:
        return "ip"
    if ioc_type == "domain":
        return "domain"
    if ioc_type == "url":
        return "url"
    return None


def _selection_value(rule_type: str, ioc_value: str) -> str:
    if rule_type != "url":
        return ioc_value
    parsed = urlparse(ioc_value)
    return parsed.hostname.lower() if parsed.hostname else ioc_value


def _mitre_tags(item: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for value in item.get("labels", []):
        label = str(value).strip().lower()
        if label.startswith("attack."):
            tags.add(label)
        elif label.startswith("mitre-attack."):
            tags.add("attack." + label.removeprefix("mitre-attack."))
    for value in item.get("x_mitre_attack_tags", []):
        tag = str(value).strip().lower()
        if tag:
            tags.add(tag if tag.startswith("attack.") else f"attack.{tag}")
    return tags


def _stix_enrichment(
    raw_bundle_json: str, ioc_value: str, ioc_type: str
) -> tuple[int | None, set[str]]:
    """Read optional confidence and MITRE tags from the matching Indicator."""
    try:
        bundle = json.loads(raw_bundle_json)
    except (TypeError, json.JSONDecodeError):
        return None, set()
    for item in bundle.get("objects", []):
        if item.get("type") != "indicator":
            continue
        try:
            value, candidate_type = indicator_value_and_type(str(item["pattern"]))
        except (KeyError, ValueError):
            continue
        if value == ioc_value and candidate_type == ioc_type:
            confidence = item.get("confidence")
            return (
                int(confidence) if confidence is not None else None,
                _mitre_tags(item),
            )
    return None, set()


def load_network_iocs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, IOCBatch]:
    """Load and batch supported network IOC rows from SQLite."""
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT ioc_value, ioc_type, raw_bundle_json
            FROM iocs
            WHERE ioc_type IN ('ip', 'ipv4', 'ipv6', 'domain', 'url')
            ORDER BY ioc_type, ioc_value
            """
        ).fetchall()
    finally:
        connection.close()

    batches: dict[str, IOCBatch] = {}
    for row in rows:
        rule_type = _rule_type(row["ioc_type"])
        if rule_type is None:
            continue
        batch = batches.setdefault(rule_type, IOCBatch())
        value = _selection_value(rule_type, row["ioc_value"])
        if value:
            batch.values.add(value)
        confidence, tags = _stix_enrichment(
            row["raw_bundle_json"], row["ioc_value"], row["ioc_type"]
        )
        if confidence is not None:
            batch.confidence = max(batch.confidence or 0, confidence)
        batch.tags.update(tags)
    return batches


def build_sigma_rules(batches: dict[str, IOCBatch]) -> list[dict[str, Any]]:
    """Build one Sigma rule per IOC group with list-based selections."""
    rules: list[dict[str, Any]] = []
    for rule_type in ("ip", "domain", "url"):
        batch = batches.get(rule_type)
        if batch is None or not batch.values:
            continue
        config = RULE_CONFIG[rule_type]
        values = sorted(batch.values)
        stable_key = f"{rule_type}|{'|'.join(values)}"
        rule: dict[str, Any] = {
            "title": config["title"],
            "id": str(uuid.uuid5(RULE_NAMESPACE, stable_key)),
            "status": "experimental",
            "description": config["description"],
            "logsource": {"category": config["category"]},
            "detection": {
                "selection": {config["field"]: values},
                "condition": "selection",
            },
            "level": (
                "high"
                if batch.confidence is not None
                and batch.confidence >= HIGH_CONFIDENCE_THRESHOLD
                else "medium"
            ),
        }
        if batch.tags:
            rule["tags"] = sorted(batch.tags)
        rules.append(rule)
    return rules


def save_sigma_rules(
    rules: Iterable[dict[str, Any]],
    *,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    generated_on: date | datetime | None = None,
) -> Path:
    """Atomically save rules as a multi-document YAML file for one date."""
    documents = list(rules)
    if not documents:
        raise ValueError("No supported network IOCs were found for Sigma generation")
    if generated_on is None:
        output_date = datetime.now(timezone.utc).date()
    elif isinstance(generated_on, datetime):
        output_date = generated_on.date()
    else:
        output_date = generated_on

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{output_date.isoformat()}.yml"
    temporary = path.with_suffix(".yml.tmp")
    temporary.write_text(
        yaml.safe_dump_all(
            documents,
            sort_keys=False,
            explicit_start=True,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def generate_sigma_rules(
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    generated_on: date | datetime | None = None,
) -> Path:
    """Load stored network IOCs and create the dated Sigma YAML artifact."""
    batches = load_network_iocs(database_path)
    rules = build_sigma_rules(batches)
    return save_sigma_rules(
        rules, output_directory=output_directory, generated_on=generated_on
    )
