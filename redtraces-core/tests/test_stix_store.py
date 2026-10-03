"""Tests for persistent STIX bundle ingestion and IOC upserts."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stix2 import Bundle, Identity, Indicator

from common.stix_generator import build_stix_bundle
from common.stix_store import STIXStore


def record(*, source: str, observed: datetime) -> dict[str, object]:
    return {
        "ioc_type": "ipv4",
        "value": "1.2.3.4",
        "platform": "telegram",
        "source": source,
        "collected_at": observed,
    }


class STIXStoreTest(unittest.TestCase):
    def test_inserts_then_updates_existing_ioc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "store.sqlite3"
            first_bundle = build_stix_bundle(
                [record(source="channel-one", observed=datetime(2026, 8, 1, tzinfo=timezone.utc))]
            )
            second_bundle = build_stix_bundle(
                [record(source="channel-two", observed=datetime(2026, 8, 2, tzinfo=timezone.utc))]
            )

            with STIXStore(database) as store:
                first = store.ingest_bundle(first_bundle)
                first_row = store.get_ioc("1.2.3.4", "ipv4")
                second = store.ingest_bundle(second_bundle)
                row = store.get_ioc("1.2.3.4", "ipv4")

                self.assertEqual(first.inserted, 1)
                self.assertEqual(first.updated, 0)
                self.assertEqual(second.inserted, 0)
                self.assertEqual(second.updated, 1)
                self.assertEqual(row["sighting_count"], 2)
                self.assertEqual(row["first_seen"], "2026-08-01T00:00:00Z")
                self.assertEqual(row["last_seen"], "2026-08-02T00:00:00Z")
                self.assertEqual(row["stix_id"], first_row["stix_id"])
                self.assertIn(second_bundle.id, row["raw_bundle_json"])

            with STIXStore(database) as reopened:
                self.assertEqual(
                    reopened.get_ioc("1.2.3.4", "ipv4")["sighting_count"], 2
                )

    def test_bundle_is_atomic_when_one_pattern_is_unsupported(self) -> None:
        identity = Identity(name="test", identity_class="system")
        valid = Indicator(
            pattern="[ipv4-addr:value = '5.6.7.8']",
            pattern_type="stix",
            valid_from=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        unsupported = Indicator(
            pattern="[email-addr:value = 'actor@example.com']",
            pattern_type="stix",
            valid_from=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        bundle = Bundle(identity, valid, unsupported)

        with tempfile.TemporaryDirectory() as directory:
            with STIXStore(Path(directory) / "store.sqlite3") as store:
                with self.assertRaises(ValueError):
                    store.ingest_bundle(bundle)
                count = store.connection.execute("SELECT COUNT(*) FROM iocs").fetchone()[0]
                self.assertEqual(count, 0)

    def test_requires_at_least_one_indicator(self) -> None:
        bundle = Bundle(Identity(name="source", identity_class="system"))
        with tempfile.TemporaryDirectory() as directory:
            with STIXStore(Path(directory) / "store.sqlite3") as store:
                with self.assertRaises(ValueError):
                    store.ingest_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
