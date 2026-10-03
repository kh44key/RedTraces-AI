"""Generate compile-validated YARA hash rules from the STIX IOC store."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import yara
except ModuleNotFoundError:  # pragma: no cover - depends on the host Python ABI
    yara = None  # type: ignore[assignment]

from common.stix_store import DEFAULT_DATABASE_PATH


DEFAULT_OUTPUT_DIRECTORY = Path("/output/yara_rules")
SUPPORTED_HASH_TYPES = {"md5", "sha1", "sha256"}
V1_LIMITATION = (
    "Hash-only YARA rules match exact files and are weak against modified samples; "
    "future versions should add strings, byte patterns, and structural conditions."
)


@dataclass(frozen=True)
class HashIOC:
    value: str
    hash_type: str
    source: str


@dataclass(frozen=True)
class YARAGenerationResult:
    path: Path
    generated_rules: int
    discarded_rules: int


def _yara_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _source_name(source_id: str | None, raw_bundle_json: str) -> str:
    try:
        bundle = json.loads(raw_bundle_json)
    except (TypeError, json.JSONDecodeError):
        return source_id or "unknown"
    for item in bundle.get("objects", []):
        if item.get("type") != "identity" or item.get("id") != source_id:
            continue
        return str(
            item.get("x_redtraces_source")
            or item.get("name")
            or source_id
            or "unknown"
        )
    return source_id or "unknown"


def load_hash_iocs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[HashIOC]:
    """Load supported file hashes from the persistent SQLite IOC store."""
    connection = sqlite3.connect(Path(database_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT ioc_value, ioc_type, source_id, raw_bundle_json
            FROM iocs
            WHERE ioc_type IN ('md5', 'sha1', 'sha256')
            ORDER BY ioc_type, ioc_value
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        HashIOC(
            value=row["ioc_value"].lower(),
            hash_type=row["ioc_type"],
            source=_source_name(row["source_id"], row["raw_bundle_json"]),
        )
        for row in rows
    ]


def build_rule_block(ioc: HashIOC, index: int, generated_on: date) -> str:
    """Build one extension-friendly YARA rule block for a file hash."""
    if ioc.hash_type not in SUPPORTED_HASH_TYPES:
        raise ValueError(f"Unsupported YARA hash type: {ioc.hash_type}")
    return f'''rule Auto_Generated_{index:04d} {{
    meta:
        description = "Auto-generated RedTraces AI exact file-hash detection"
        source = "{_yara_string(ioc.source)}"
        date = "{generated_on.isoformat()}"
        hash_type = "{ioc.hash_type}"
        hash_value = "{ioc.value}"
    condition:
        hash.{ioc.hash_type}(0, filesize) == "{ioc.value}"
}}'''


def _document(rule_blocks: Iterable[str]) -> str:
    blocks = list(rule_blocks)
    return (
        'import "hash"\n\n'
        f"// YARA generator v1 limitation: {V1_LIMITATION}\n\n"
        + "\n\n".join(blocks)
        + "\n"
    )


def _yara_engine():
    if yara is None:
        raise RuntimeError(
            "yara-python is required for compilation. Use the Python 3.12 "
            "Docker service or install Microsoft C++ Build Tools for this "
            "Python version."
        )
    return yara


def compile_rule_blocks(rule_blocks: Iterable[str]) -> tuple[list[str], int]:
    """Compile each block independently and discard only invalid blocks."""
    engine = _yara_engine()
    valid: list[str] = []
    discarded = 0
    for block in rule_blocks:
        try:
            engine.compile(source=_document([block]))
        except engine.Error:
            discarded += 1
            continue
        valid.append(block)
    return valid, discarded


def save_yara_rules(
    iocs: Iterable[HashIOC],
    *,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    generated_on: date | datetime | None = None,
) -> YARAGenerationResult:
    """Compile and atomically save one dated YARA file for all valid hashes."""
    if generated_on is None:
        output_date = datetime.now(timezone.utc).date()
    elif isinstance(generated_on, datetime):
        output_date = generated_on.date()
    else:
        output_date = generated_on

    blocks = [
        build_rule_block(ioc, index, output_date)
        for index, ioc in enumerate(iocs, start=1)
    ]
    valid_blocks, discarded = compile_rule_blocks(blocks)
    if not valid_blocks:
        raise ValueError("No valid file-hash YARA rules were available to save")

    source = _document(valid_blocks)
    engine = _yara_engine()
    try:
        engine.compile(source=source)
    except engine.Error as error:
        raise ValueError(f"Combined YARA rule file failed compilation: {error}") from error

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{output_date.isoformat()}.yar"
    temporary = path.with_suffix(".yar.tmp")
    temporary.write_text(source, encoding="utf-8")
    temporary.replace(path)
    return YARAGenerationResult(
        path=path,
        generated_rules=len(valid_blocks),
        discarded_rules=discarded,
    )


def generate_yara_rules(
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    generated_on: date | datetime | None = None,
) -> YARAGenerationResult:
    """Load stored hashes and generate the dated, compiled YARA artifact."""
    return save_yara_rules(
        load_hash_iocs(database_path),
        output_directory=output_directory,
        generated_on=generated_on,
    )
