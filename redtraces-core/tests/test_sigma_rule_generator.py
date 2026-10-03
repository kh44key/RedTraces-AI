"""Tests for batched Sigma YAML generation from the STIX SQLite store."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from common.sigma_rule_generator import generate_sigma_rules
from common.stix_generator import build_stix_bundle
from common.stix_store import STIXStore


class SigmaRuleGeneratorTest(unittest.TestCase):
    def test_batches_network_iocs_by_rule_type(self) -> None:
        records = [
            {
                "ioc_type": "ipv4",
                "value": "1.2.3.4",
                "platform": "telegram",
                "source": "channel",
                "confidence": 50,
            },
            {
                "ioc_type": "ipv6",
                "value": "2001:db8::1",
                "platform": "telegram",
                "source": "channel",
                "confidence": 80,
            },
            {
                "ioc_type": "domain",
                "value": "evil.example",
                "platform": "darkweb",
                "source": "forum.onion",
            },
            {
                "ioc_type": "url",
                "value": "https://payload.example/dropper",
                "platform": "reddit",
                "source": "netsec",
            },
            {
                "ioc_type": "sha256",
                "value": "a" * 64,
                "platform": "telegram",
                "source": "channel",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with STIXStore(root / "store.sqlite3") as store:
                store.ingest_bundle(build_stix_bundle(records))

            path = generate_sigma_rules(
                database_path=root / "store.sqlite3",
                output_directory=root / "rules",
                generated_on=date(2026, 8, 2),
            )
            documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))

            self.assertEqual(path.name, "2026-08-02.yml")
            self.assertEqual(len(documents), 3)
            by_category = {item["logsource"]["category"]: item for item in documents}

            firewall = by_category["firewall"]
            self.assertEqual(
                firewall["detection"]["selection"]["destination.ip"],
                ["1.2.3.4", "2001:db8::1"],
            )
            self.assertEqual(firewall["detection"]["condition"], "selection")
            self.assertEqual(firewall["level"], "high")

            dns = by_category["dns"]
            self.assertEqual(
                dns["detection"]["selection"]["dns.query.name"],
                ["evil.example"],
            )
            self.assertEqual(dns["level"], "medium")

            proxy = by_category["proxy"]
            self.assertEqual(
                proxy["detection"]["selection"]["url.domain"],
                ["payload.example"],
            )
            self.assertNotIn("a" * 64, path.read_text(encoding="utf-8"))

    def test_fails_without_network_iocs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with STIXStore(root / "store.sqlite3") as store:
                store.ingest_bundle(
                    build_stix_bundle(
                        [
                            {
                                "ioc_type": "sha256",
                                "value": "b" * 64,
                                "platform": "telegram",
                                "source": "channel",
                            }
                        ]
                    )
                )
            with self.assertRaises(ValueError):
                generate_sigma_rules(
                    database_path=root / "store.sqlite3",
                    output_directory=root / "rules",
                )


if __name__ == "__main__":
    unittest.main()
