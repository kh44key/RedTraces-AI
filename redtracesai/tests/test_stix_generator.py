"""Tests for normalized IOC to STIX 2.1 conversion."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stix2 import parse

from common.ioc_normalizer import normalize_ioc_groups
from common.stix_generator import indicator_pattern, save_stix_bundle


class STIXGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.records = normalize_ioc_groups(
            {
                "ipv4": ["1.2.3.4"],
                "domains": ["evil.example"],
                "sha256": ["a" * 64],
            },
            platform="telegram",
            source="falconfeedsio",
            source_url="https://t.me/falconfeedsio/7",
            message_id=7,
            collected_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )

    def test_patterns_match_ioc_types(self) -> None:
        self.assertEqual(
            indicator_pattern(self.records[0]), "[ipv4-addr:value = '1.2.3.4']"
        )
        self.assertEqual(
            indicator_pattern(self.records[2]),
            f"[file:hashes.'SHA-256' = '{'a' * 64}']",
        )

    def test_saves_valid_bundle_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = save_stix_bundle(
                self.records,
                output_directory=directory,
                timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
            )
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            bundle = parse(payload, allow_custom=True)
            object_types = [item.type for item in bundle.objects]
            self.assertEqual(object_types.count("identity"), 1)
            self.assertEqual(object_types.count("indicator"), 3)
            self.assertEqual(object_types.count("relationship"), 3)
            for relationship in (
                item for item in bundle.objects if item.type == "relationship"
            ):
                self.assertEqual(relationship.relationship_type, "indicates")

    def test_rejects_invalid_hash_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_stix_bundle(
                    [
                        {
                            "ioc_type": "sha256",
                            "value": "not-a-hash",
                            "platform": "darkweb",
                            "source": "example.onion",
                        }
                    ],
                    output_directory=directory,
                )
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
