"""Convert Sigma rules and push detection artifacts to supported SIEM APIs."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
import yaml

from common.stix_store import DEFAULT_DATABASE_PATH


log = logging.getLogger(__name__)
SUPPORTED_SIEMS = {"splunk", "elastic", "wazuh", "qradar"}


@dataclass(frozen=True)
class SIEMConfig:
    siem_type: str
    url: str
    api_key: str | None
    username: str | None
    password: str | None
    verify_ssl: bool
    timeout_seconds: int
    rule_endpoint: str | None
    yara_endpoint: str | None

    @classmethod
    def from_env(cls) -> "SIEMConfig":
        siem_type = os.getenv("SIEM_TYPE", "").strip().lower()
        url = os.getenv("SIEM_URL", "").strip().rstrip("/")
        if siem_type not in SUPPORTED_SIEMS:
            raise ValueError("SIEM_TYPE must be splunk, elastic, wazuh, or qradar")
        if not url:
            raise ValueError("SIEM_URL is required")
        return cls(
            siem_type=siem_type,
            url=url,
            api_key=os.getenv("SIEM_API_KEY") or None,
            username=os.getenv("SIEM_USER") or None,
            password=os.getenv("SIEM_PASS") or None,
            verify_ssl=os.getenv("SIEM_VERIFY_SSL", "true").lower()
            not in {"0", "false", "no"},
            timeout_seconds=int(os.getenv("SIEM_TIMEOUT_SECONDS", "30")),
            rule_endpoint=os.getenv("SIEM_RULE_ENDPOINT") or None,
            yara_endpoint=os.getenv("SIEM_YARA_ENDPOINT") or None,
        )


@dataclass(frozen=True)
class PushResult:
    status: str
    siem_type: str
    artifact_type: str
    artifact_id: str | None
    endpoint: str | None
    response_code: int | None
    message: str


class PushLog:
    """Persistent audit trail in the local STIX SQLite database."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS siem_push_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempted_at TEXT NOT NULL,
                    siem_type TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    artifact_id TEXT,
                    status TEXT NOT NULL,
                    endpoint TEXT,
                    response_code INTEGER,
                    message TEXT NOT NULL
                )
                """
            )
            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_siem_push_log_attempted_at
                ON siem_push_log (attempted_at)
                """
            )

    def record(self, result: PushResult) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO siem_push_log (
                    attempted_at, siem_type, artifact_type, artifact_id,
                    status, endpoint, response_code, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    result.siem_type,
                    result.artifact_type,
                    result.artifact_id,
                    result.status,
                    result.endpoint,
                    result.response_code,
                    result.message,
                ),
            )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "PushLog":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


BACKEND_IMPORTS: dict[str, list[tuple[str, str]]] = {
    "splunk": [
        ("sigma.backends.splunk.splunk", "SplunkBackend"),
        ("sigma.backends.splunk", "SplunkBackend"),
    ],
    "elastic": [
        ("sigma.backends.elasticsearch.elasticsearch_lucene", "LuceneBackend"),
        ("sigma.backends.elasticsearch", "LuceneBackend"),
    ],
    "wazuh": [
        ("sigma.backends.elasticsearch.elasticsearch_lucene", "LuceneBackend"),
        ("sigma.backends.elasticsearch", "LuceneBackend"),
    ],
    "qradar": [
        ("sigma.backends.qradar", "QRadarBackend"),
        ("sigma.backends.qradar.qradar", "QRadarBackend"),
    ],
}


def _backend(siem_type: str):
    errors: list[str] = []
    for module_name, class_name in BACKEND_IMPORTS[siem_type]:
        try:
            backend_class = getattr(import_module(module_name), class_name)
            return backend_class()
        except (ImportError, AttributeError) as error:
            errors.append(f"{module_name}.{class_name}: {error}")
    raise RuntimeError(
        f"No pySigma backend available for {siem_type}. " + "; ".join(errors)
    )


def convert_sigma_rule(rule_yaml: str, siem_type: str) -> str:
    """Convert one Sigma YAML document using the selected pySigma backend."""
    from sigma.collection import SigmaCollection

    collection = SigmaCollection.from_yaml(rule_yaml)
    try:
        backend = _backend(siem_type)
    except RuntimeError as error:
        if siem_type == "qradar":
            raise NotImplementedError(
                "The available QRadar pySigma backend requires a legacy, "
                "incompatible pySigma release. Run QRadar conversion in an "
                "isolated adapter service and set SIEM_RULE_ENDPOINT."
            ) from error
        raise
    queries = backend.convert(collection)
    if not queries:
        raise ValueError("pySigma backend produced no native query")
    return "\n".join(str(query) for query in queries)


def _rule(rule_yaml: str) -> dict[str, Any]:
    value = yaml.safe_load(rule_yaml)
    if not isinstance(value, dict):
        raise ValueError("Sigma input must contain exactly one YAML rule object")
    for field in ("title", "id", "description", "level"):
        if field not in value:
            raise ValueError(f"Sigma rule is missing required field: {field}")
    return value


def _headers(config: SIEMConfig) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if config.api_key:
        if config.siem_type == "splunk":
            headers["Authorization"] = f"Splunk {config.api_key}"
        elif config.siem_type == "qradar":
            headers["SEC"] = config.api_key
            headers["Version"] = os.getenv("SIEM_QRADAR_API_VERSION", "24.0")
        else:
            headers["Authorization"] = (
                f"ApiKey {config.api_key}"
                if config.siem_type == "elastic"
                else f"Bearer {config.api_key}"
            )
    return headers


def _auth(config: SIEMConfig) -> tuple[str, str] | None:
    if config.api_key:
        return None
    if config.username and config.password:
        return config.username, config.password
    raise ValueError("Set SIEM_API_KEY or both SIEM_USER and SIEM_PASS")


def _request(
    session: requests.Session,
    config: SIEMConfig,
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> requests.Response:
    response = session.request(
        method,
        endpoint,
        headers={**_headers(config), **kwargs.pop("headers", {})},
        auth=_auth(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
        **kwargs,
    )
    response.raise_for_status()
    return response


def _splunk_push(
    rule: dict[str, Any], query: str, config: SIEMConfig, session: requests.Session
) -> tuple[str, requests.Response]:
    owner = quote(os.getenv("SIEM_SPLUNK_OWNER", "nobody"), safe="")
    app = quote(os.getenv("SIEM_SPLUNK_APP", "search"), safe="")
    endpoint = config.rule_endpoint or f"{config.url}/servicesNS/{owner}/{app}/saved/searches"
    response = _request(
        session,
        config,
        "POST",
        endpoint,
        data={
            "name": rule["title"],
            "search": query,
            "description": rule["description"],
            "is_scheduled": "1",
            "cron_schedule": os.getenv("SIEM_SPLUNK_CRON", "*/5 * * * *"),
            "disabled": os.getenv("SIEM_RULES_ENABLED", "false").lower()
            in {"0", "false", "no"},
            "output_mode": "json",
        },
    )
    return endpoint, response


def _elastic_push(
    rule: dict[str, Any], query: str, config: SIEMConfig, session: requests.Session
) -> tuple[str, requests.Response]:
    endpoint = config.rule_endpoint or f"{config.url}/api/detection_engine/rules"
    level = str(rule["level"]).lower()
    response = _request(
        session,
        config,
        "POST",
        endpoint,
        headers={"Content-Type": "application/json", "kbn-xsrf": "true"},
        json={
            "rule_id": str(rule["id"]),
            "name": rule["title"],
            "description": rule["description"],
            "risk_score": {"low": 21, "medium": 47, "high": 73, "critical": 99}.get(level, 47),
            "severity": level if level in {"low", "medium", "high", "critical"} else "medium",
            "type": "query",
            "language": "lucene",
            "query": query,
            "index": [
                item.strip()
                for item in os.getenv("SIEM_ELASTIC_INDICES", "logs-*,filebeat-*,packetbeat-*").split(",")
                if item.strip()
            ],
            "interval": os.getenv("SIEM_RULE_INTERVAL", "5m"),
            "from": os.getenv("SIEM_RULE_FROM", "now-6m"),
            "enabled": os.getenv("SIEM_RULES_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            "tags": list(rule.get("tags", [])),
        },
    )
    return endpoint, response


def _wazuh_push(
    rule: dict[str, Any], query: str, config: SIEMConfig, session: requests.Session
) -> tuple[str, requests.Response]:
    endpoint = config.rule_endpoint or f"{config.url}/_plugins/_alerting/monitors"
    response = _request(
        session,
        config,
        "POST",
        endpoint,
        headers={"Content-Type": "application/json"},
        json={
            "type": "monitor",
            "name": rule["title"],
            "enabled": os.getenv("SIEM_RULES_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            "schedule": {"period": {"interval": 5, "unit": "MINUTES"}},
            "inputs": [
                {
                    "search": {
                        "indices": [os.getenv("SIEM_WAZUH_INDEX", "wazuh-alerts-*")],
                        "query": {"size": 0, "query": {"query_string": {"query": query}}},
                    }
                }
            ],
            "triggers": [],
        },
    )
    return endpoint, response


def _qradar_push(
    rule: dict[str, Any], query: str, config: SIEMConfig, session: requests.Session
) -> tuple[str, requests.Response]:
    if not config.rule_endpoint:
        raise NotImplementedError(
            "QRadar has no universal REST endpoint for creating correlation rules; "
            "set SIEM_RULE_ENDPOINT to an approved QRadar integration/app endpoint."
        )
    response = _request(
        session,
        config,
        "POST",
        config.rule_endpoint,
        headers={"Content-Type": "application/json"},
        json={
            "name": rule["title"],
            "description": rule["description"],
            "rule_id": str(rule["id"]),
            "aql": query,
            "sigma": rule,
        },
    )
    return config.rule_endpoint, response


PUSHERS = {
    "splunk": _splunk_push,
    "elastic": _elastic_push,
    "wazuh": _wazuh_push,
    "qradar": _qradar_push,
}


def push_sigma_rule(
    rule_yaml: str,
    *,
    config: SIEMConfig | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    session: requests.Session | None = None,
) -> PushResult:
    """Convert and push one Sigma rule, recording every outcome locally."""
    try:
        selected = config or SIEMConfig.from_env()
    except Exception as error:
        result = PushResult(
            "failure",
            os.getenv("SIEM_TYPE", "unknown") or "unknown",
            "sigma",
            None,
            None,
            None,
            f"SIEM configuration error: {error}",
        )
        with PushLog(database_path) as audit:
            audit.record(result)
        return result
    rule: dict[str, Any] = {}
    endpoint: str | None = selected.rule_endpoint
    try:
        rule = _rule(rule_yaml)
        query = convert_sigma_rule(rule_yaml, selected.siem_type)
        endpoint, response = PUSHERS[selected.siem_type](
            rule, query, selected, session or requests.Session()
        )
        result = PushResult(
            status="success",
            siem_type=selected.siem_type,
            artifact_type="sigma",
            artifact_id=str(rule["id"]),
            endpoint=endpoint,
            response_code=response.status_code,
            message="Sigma rule converted and pushed successfully",
        )
    except NotImplementedError as error:
        result = PushResult(
            "manual_required", selected.siem_type, "sigma",
            str(rule.get("id")) if rule else None, endpoint, None, str(error)
        )
        log.warning("siem_sigma_manual_deployment", extra={"message_detail": str(error)})
    except Exception as error:
        result = PushResult(
            "failure", selected.siem_type, "sigma",
            str(rule.get("id")) if rule else None, endpoint,
            getattr(getattr(error, "response", None), "status_code", None), str(error)
        )
        log.exception("siem_sigma_push_failed")
    with PushLog(database_path) as audit:
        audit.record(result)
    return result


def push_yara_rule(
    rule_path: str | Path,
    *,
    config: SIEMConfig | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    session: requests.Session | None = None,
) -> PushResult:
    """Upload YARA only to an explicitly configured endpoint; otherwise log manual work."""
    try:
        selected = config or SIEMConfig.from_env()
    except Exception as error:
        result = PushResult(
            "failure",
            os.getenv("SIEM_TYPE", "unknown") or "unknown",
            "yara",
            Path(rule_path).name,
            None,
            None,
            f"SIEM configuration error: {error}",
        )
        with PushLog(database_path) as audit:
            audit.record(result)
        return result
    path = Path(rule_path)
    endpoint = selected.yara_endpoint
    try:
        if not path.is_file():
            raise FileNotFoundError(path)
        if not endpoint:
            raise NotImplementedError(
                f"{selected.siem_type} has no configured YARA/EDR upload endpoint; "
                f"manual deployment required: {path}"
            )
        with path.open("rb") as handle:
            response = _request(
                session or requests.Session(),
                selected,
                "POST",
                endpoint,
                files={"file": (path.name, handle, "application/octet-stream")},
            )
        result = PushResult(
            "success", selected.siem_type, "yara", path.name,
            endpoint, response.status_code, "YARA rule uploaded successfully"
        )
    except NotImplementedError as error:
        result = PushResult(
            "manual_required", selected.siem_type, "yara", path.name,
            endpoint, None, str(error)
        )
        log.warning("siem_yara_manual_deployment", extra={"path": str(path)})
    except Exception as error:
        result = PushResult(
            "failure", selected.siem_type, "yara", path.name,
            endpoint, getattr(getattr(error, "response", None), "status_code", None), str(error)
        )
        log.exception("siem_yara_push_failed")
    with PushLog(database_path) as audit:
        audit.record(result)
    return result


def push_sigma_file(
    path: str | Path,
    **kwargs: Any,
) -> list[PushResult]:
    """Push every YAML document from a generated Sigma file."""
    content = Path(path).read_text(encoding="utf-8")
    return [
        push_sigma_rule(yaml.safe_dump(rule, sort_keys=False), **kwargs)
        for rule in yaml.safe_load_all(content)
        if rule
    ]
