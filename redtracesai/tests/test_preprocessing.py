"""Tests for Layer 3 normalization and defanging reversal."""

from __future__ import annotations

import unittest

from common.ioc import enrich_metadata, extract_iocs
from common.preprocessing import preprocess_text


class PreprocessingTest(unittest.TestCase):
    def test_refangs_protocols_dots_and_scheme_separators(self) -> None:
        result = preprocess_text(
            "hxxps[://]c2[.]example/path 192(.)0(.)2(.)45 "
            "backup dot example meow://mirror[dot]example"
        )

        self.assertIn("https://c2.example/path", result.text)
        self.assertIn("192.0.2.45", result.text)
        self.assertIn("backup.example", result.text)
        self.assertIn("http://mirror.example", result.text)
        self.assertIn("hxxps_refanged", result.transformations)
        self.assertIn("bracketed_dot_refanged", result.transformations)

    def test_normalizes_unicode_html_and_invisible_characters(self) -> None:
        result = preprocess_text("Ａ&amp;B\u200b\t  alert")
        self.assertEqual(result.text, "A&B alert")
        self.assertIn("unicode_nfkc", result.transformations)
        self.assertIn("html_entities_decoded", result.transformations)
        self.assertIn("zero_width_removed", result.transformations)

    def test_preserves_raw_input_outside_metadata_helper(self) -> None:
        raw = "C2 hxxps://node[.]example at 198[.]51[.]100[.]8"
        metadata = enrich_metadata({"message_id": 1}, raw)

        self.assertEqual(raw, "C2 hxxps://node[.]example at 198[.]51[.]100[.]8")
        self.assertEqual(
            metadata["preprocessing"]["normalized_text"],
            "C2 https://node.example at 198.51.100.8",
        )
        self.assertIn("node.example", metadata["iocs"]["domains"])
        self.assertIn("198.51.100.8", metadata["iocs"]["ipv4"])

    def test_extraction_is_idempotent_after_preprocessing(self) -> None:
        prepared = preprocess_text("hxxp://a[.]example").text
        self.assertEqual(extract_iocs(prepared), extract_iocs("hxxp://a[.]example"))


if __name__ == "__main__":
    unittest.main()
