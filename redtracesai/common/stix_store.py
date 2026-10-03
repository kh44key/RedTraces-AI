"""Persistent SQLite store for IOC Indicators from STIX 2.1 bundles."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stix2 import Bundle, parse

from common.stix_generator import validate_bundle


DEFAULT_DATABASE_PATH = Path("/output/stix_store.sqlite3")
VALUE_PATTERN = re.compile(
    r"^\[(ipv4-addr|ipv6-addr|domain-name|url):value\s*=\s*'((?:\\.|[^'])*)'\]$"
)
HASH_PATTERN = re.compile(
    r"^\[file:hashes\.'(MD5|SHA-1|SHA-256)'\s*=\s*'([0-9a-fA-F]+)'\]$"
)
OBJECT_TYPES = {
    "ipv4-addr": "ipv4",
    "ipv6-addr": "ipv6",
    "domain-name": "domain",
    "url": "url",
}
HASH_TYPES = {"MD5": "md5", "SHA-1": "sha1", "SHA-256": "sha256"}


@dataclass(frozen=True)
class IngestionResult:
    inserted: int
    updated: int
    total_indicators: int


def _unescape_stix_string(value: str) -> str:
    """Reverse the escaping performed for STIX single-quoted literals."""
    output: list[str] = []
    escaped = False
    for character in value:
        if escaped:
            output.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        else:
            output.append(character)
    if escaped:
        output.append("\\")
    return "".join(output)


def indicator_value_and_type(pattern: str) -> tuple[str, str]:
    """Extract the normalized value/type from a supported generated pattern."""
    match = VALUE_PATTERN.fullmatch(pattern)
    if match:
        object_type, escaped_value = match.groups()
        return _unescape_stix_string(escaped_value), OBJECT_TYPES[object_type]

    match = HASH_PATTERN.fullmatch(pattern)
    if match:
        algorithm, value = match.groups()
        return value.lower(), HASH_TYPES[algorithm]

    raise ValueError(f"Unsupported Indicator pattern for IOC storage: {pattern}")


def _timestamp(value: Any) -> str:
    """Return an aware UTC timestamp in stable ISO-8601 form."""
    if value is None:
        moment = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_bundle(value: Bundle | str | bytes | dict[str, Any]) -> Bundle:
    if isinstance(value, Bundle):
        bundle = value
    else:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        bundle = parse(value, version="2.1", allow_custom=True)
    if not isinstance(bundle, Bundle):
        raise ValueError("STIX input must be a Bundle object")
    validate_bundle(bundle)
    return bundle


class STIXStore:
    """Transactional SQLite-backed IOC store."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS iocs (
                    stix_id TEXT NOT NULL,
                    ioc_value TEXT NOT NULL,
                    ioc_type TEXT NOT NULL,
                    source_id TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    sighting_count INTEGER NOT NULL DEFAULT 1
                        CHECK (sighting_count >= 1),
                    raw_bundle_json TEXT NOT NULL,
                    UNIQUE (ioc_value, ioc_type)
                )
                """
            )
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_iocs_type ON iocs (ioc_type)"
            )
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_iocs_last_seen ON iocs (last_seen)"
            )

    def ingest_bundle(
        self, bundle_input: Bundle | str | bytes | dict[str, Any]
    ) -> IngestionResult:
        """Validate and atomically upsert every Indicator in one bundle."""
        bundle = _load_bundle(bundle_input)
        raw_bundle = json.dumps(json.loads(bundle.serialize()), separators=(",", ":"))

        provenance: dict[str, str] = {}
        for item in bundle.objects:
            if item.type == "relationship" and item.relationship_type == "indicates":
                provenance[item.source_ref] = item.target_ref

        rows: list[tuple[str, str, str, str | None, str]] = []
        for item in bundle.objects:
            if item.type != "indicator":
                continue
            ioc_value, ioc_type = indicator_value_and_type(item.pattern)
            source_id = provenance.get(item.id) or getattr(item, "created_by_ref", None)
            observed_at = _timestamp(getattr(item, "valid_from", None))
            rows.append((item.id, ioc_value, ioc_type, source_id, observed_at))

        if not rows:
            raise ValueError("STIX bundle contains no Indicator objects")

        inserted = 0
        updated = 0
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            for stix_id, ioc_value, ioc_type, source_id, observed_at in rows:
                exists = self.connection.execute(
                    "SELECT 1 FROM iocs WHERE ioc_value = ? AND ioc_type = ?",
                    (ioc_value, ioc_type),
                ).fetchone()
                if exists is None:
                    inserted += 1
                else:
                    updated += 1
                self.connection.execute(
                    """
                    INSERT INTO iocs (
                        stix_id, ioc_value, ioc_type, source_id,
                        first_seen, last_seen, sighting_count, raw_bundle_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(ioc_value, ioc_type) DO UPDATE SET
                        last_seen = CASE
                            WHEN excluded.last_seen > iocs.last_seen
                            THEN excluded.last_seen ELSE iocs.last_seen
                        END,
                        source_id = excluded.source_id,
                        sighting_count = iocs.sighting_count + 1,
                        raw_bundle_json = excluded.raw_bundle_json
                    """,
                    (
                        stix_id,
                        ioc_value,
                        ioc_type,
                        source_id,
                        observed_at,
                        observed_at,
                        raw_bundle,
                    ),
                )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

        return IngestionResult(
            inserted=inserted,
            updated=updated,
            total_indicators=len(rows),
        )

    def ingest_file(self, bundle_path: str | Path) -> IngestionResult:
        return self.ingest_bundle(Path(bundle_path).read_text(encoding="utf-8"))

    def get_ioc(self, ioc_value: str, ioc_type: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM iocs WHERE ioc_value = ? AND ioc_type = ?",
            (ioc_value, ioc_type),
        ).fetchone()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "STIXStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
