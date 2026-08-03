"""Tests for multi-provider SIEM pushing and persistent audit logging."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import requests

from common.siem_pusher import (
    SIEMConfig,
    convert_sigma_rule,
    push_sigma_rule,
    push_yara_rule,
)


RULE = """title: Test IOC Rule
id: 11111111-1111-4111-8111-111111111111
status: experimental
description: Test generated rule
logsource:
  category: firewall
detection:
  selection:
    destination.ip:
      - 1.2.3.4
  condition: selection
level: medium
"""


class FakeSession:
    def __init__(self, status_code: int = 201) -> None:
        self.status_code = status_code
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, endpoint: str, **kwargs):
        self.calls.append({"method": method, "endpoint": endpoint, **kwargs})
        response = requests.Response()
        response.status_code = self.status_code
        response.url = endpoint
        response._content = b'{}'
        if self.status_code >= 400:
            response.reason = "test failure"
        return response


def config(siem_type: str, **overrides) -> SIEMConfig:
    values = {
        "siem_type": siem_type,
        "url": "https://siem.example",
        "api_key": "secret-token",
        "username": None,
        "password": None,
        "verify_ssl": True,
        "timeout_seconds": 30,
        "rule_endpoint": None,
        "yara_endpoint": None,
    }
    values.update(overrides)
    return SIEMConfig(**values)


def log_rows(database: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM siem_push_log ORDER BY id").fetchall()
    finally:
        connection.close()


class SIEMPusherTest(unittest.TestCase):
    def test_configuration_failure_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "audit.sqlite3"
            with patch.dict(
                "os.environ", {"SIEM_TYPE": "", "SIEM_URL": ""}, clear=False
            ):
                result = push_sigma_rule(RULE, database_path=database)
            self.assertEqual(result.status, "failure")
            self.assertEqual(log_rows(database)[0]["status"], "failure")

    def test_installed_current_backends_convert_generated_rule(self) -> None:
        for siem_type in ("splunk", "elastic", "wazuh"):
            with self.subTest(siem_type=siem_type):
                query = convert_sigma_rule(RULE, siem_type)
                self.assertIsInstance(query, str)
                self.assertTrue(query.strip())

    @patch("common.siem_pusher.convert_sigma_rule", return_value="destination.ip=1.2.3.4")
    def test_pushes_splunk_saved_search_and_logs_success(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "audit.sqlite3"
            session = FakeSession()
            result = push_sigma_rule(
                RULE, config=config("splunk"), database_path=database, session=session
            )
            self.assertEqual(result.status, "success")
            self.assertIn("/servicesNS/nobody/search/saved/searches", session.calls[0]["endpoint"])
            self.assertEqual(session.calls[0]["data"]["search"], "destination.ip=1.2.3.4")
            self.assertEqual(log_rows(database)[0]["status"], "success")

    @patch("common.siem_pusher.convert_sigma_rule", return_value="destination.ip:1.2.3.4")
    def test_pushes_elastic_detection_rule(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession()
            result = push_sigma_rule(
                RULE,
                config=config("elastic"),
                database_path=Path(directory) / "audit.sqlite3",
                session=session,
            )
            payload = session.calls[0]["json"]
            self.assertEqual(result.status, "success")
            self.assertEqual(session.calls[0]["endpoint"], "https://siem.example/api/detection_engine/rules")
            self.assertEqual(payload["language"], "lucene")
            self.assertEqual(payload["query"], "destination.ip:1.2.3.4")

    @patch("common.siem_pusher.convert_sigma_rule", return_value="destination.ip:1.2.3.4")
    def test_pushes_wazuh_indexer_monitor(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession()
            result = push_sigma_rule(
                RULE,
                config=config("wazuh"),
                database_path=Path(directory) / "audit.sqlite3",
                session=session,
            )
            self.assertEqual(result.status, "success")
            self.assertTrue(str(session.calls[0]["endpoint"]).endswith("/_plugins/_alerting/monitors"))
            query = session.calls[0]["json"]["inputs"][0]["search"]["query"]
            self.assertEqual(query["query"]["query_string"]["query"], "destination.ip:1.2.3.4")

    @patch("common.siem_pusher.convert_sigma_rule", return_value="SELECT * FROM events")
    def test_qradar_without_approved_endpoint_is_manual(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "audit.sqlite3"
            result = push_sigma_rule(
                RULE, config=config("qradar"), database_path=database, session=FakeSession()
            )
            self.assertEqual(result.status, "manual_required")
            self.assertEqual(log_rows(database)[0]["status"], "manual_required")

    @patch("common.siem_pusher.convert_sigma_rule", return_value="SELECT * FROM events")
    def test_qradar_custom_endpoint_pushes_aql(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession()
            result = push_sigma_rule(
                RULE,
                config=config("qradar", rule_endpoint="https://siem.example/custom/rules"),
                database_path=Path(directory) / "audit.sqlite3",
                session=session,
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(session.calls[0]["json"]["aql"], "SELECT * FROM events")

    def test_yara_without_endpoint_logs_manual_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "rule.yar"
            path.write_text("rule test { condition: true }", encoding="utf-8")
            result = push_yara_rule(
                path, config=config("splunk"), database_path=root / "audit.sqlite3"
            )
            self.assertEqual(result.status, "manual_required")
            self.assertIn(str(path), result.message)

    @patch("common.siem_pusher.convert_sigma_rule", return_value="query")
    def test_http_failure_is_logged(self, _convert) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "audit.sqlite3"
            result = push_sigma_rule(
                RULE,
                config=config("elastic"),
                database_path=database,
                session=FakeSession(status_code=500),
            )
            self.assertEqual(result.status, "failure")
            self.assertEqual(result.response_code, 500)
            self.assertEqual(log_rows(database)[0]["status"], "failure")


if __name__ == "__main__":
    unittest.main()
