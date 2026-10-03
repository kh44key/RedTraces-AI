"""Tests for IOC extraction and normalization."""

from __future__ import annotations

import unittest

from common.ioc import enrich_metadata, extract_iocs


class IOCExtractionTest(unittest.TestCase):
    def test_extracts_hashes_urls_ips_and_domains(self) -> None:
        sha256 = "a" * 64
        sha1 = "b" * 40
        md5 = "c" * 32
        text = (
            f"Hashes {sha256} {sha1} {md5}. "
            "C2 hxxps://evil[.]example/panel and 198.51.100.42. "
            "Fallback malware-control.example and 2001:db8::8."
        )

        iocs = extract_iocs(text)

        self.assertEqual(iocs["sha256"], [sha256])
        self.assertEqual(iocs["sha1"], [sha1])
        self.assertEqual(iocs["md5"], [md5])
        self.assertIn("https://evil.example/panel", iocs["urls"])
        self.assertIn("198.51.100.42", iocs["ipv4"])
        self.assertIn("2001:db8::8", iocs["ipv6"])
        self.assertIn("evil.example", iocs["domains"])
        self.assertIn("malware-control.example", iocs["domains"])

    def test_rejects_invalid_ips_and_deduplicates(self) -> None:
        iocs = extract_iocs(
            "bad 999.999.999.999 good.example good[.]example file.exe"
        )
        self.assertEqual(iocs["ipv4"], [])
        self.assertEqual(iocs["domains"], ["good.example"])

    def test_metadata_includes_ioc_count(self) -> None:
        metadata = enrich_metadata(
            {"message_id": 7}, "Contact https://ioc.example and 203.0.113.8"
        )
        self.assertEqual(metadata["message_id"], 7)
        self.assertGreaterEqual(metadata["ioc_count"], 3)


if __name__ == "__main__":
    unittest.main()
