"""Tests for Layer 2 noise filtering and language labels."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from common.noise import analyze_noise, detect_language, normalize_text


class NoiseFilterTest(unittest.TestCase):
    def test_normalizes_case_and_whitespace(self) -> None:
        self.assertEqual(normalize_text("  Malware\n  Alert "), "malware alert")

    def test_filters_empty_and_low_signal_text(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOISE_FILTER_ENABLED": "true",
                "NOISE_MIN_TEXT_LENGTH": "12",
            },
            clear=False,
        ):
            self.assertEqual(analyze_noise("").reason, "empty")
            self.assertEqual(analyze_noise("hello").reason, "low_signal")

    def test_preserves_short_iocs_and_attachment_messages(self) -> None:
        self.assertTrue(analyze_noise("8.8.8.8").accepted)
        self.assertTrue(analyze_noise("", has_attachments=True).accepted)

    def test_detects_workflow_script_languages(self) -> None:
        self.assertEqual(detect_language("Обнаружена новая вредоносная программа"), "ru")
        self.assertEqual(detect_language("检测到新的恶意软件活动"), "zh")
        self.assertEqual(detect_language("یک بدافزار جدید شناسایی شد"), "fa")
        self.assertEqual(detect_language("تم اكتشاف برنامج ضار جديد"), "ar")

    def test_filters_repetition_spam(self) -> None:
        self.assertEqual(
            analyze_noise(
                "malware malware malware malware malware malware malware malware"
            ).reason,
            "repeated_tokens",
        )


if __name__ == "__main__":
    unittest.main()
