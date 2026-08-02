"""Tests for Layer 2 noise filtering and language labels."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from common import noise
from common.noise import analyze_noise, detect_language, detect_language_details, normalize_text


class _FastTextFixture:
    def predict(self, _text: str, *, k: int) -> tuple[list[str], list[float]]:
        return ["__label__en"], [0.99]


class _SpamFixture:
    classes_ = [0, 1]

    def predict_proba(self, _texts: list[str]) -> list[list[float]]:
        return [[0.05, 0.95]]


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

    def test_fasttext_label_is_used_when_model_is_available(self) -> None:
        with patch("common.noise._load_fasttext_model", return_value=_FastTextFixture()):
            language, detector, confidence = detect_language_details(
                "A detailed threat intelligence report about a malware campaign."
            )
        self.assertEqual(language, "en")
        self.assertEqual(detector, "fasttext_lid176")
        self.assertEqual(confidence, 0.99)

    def test_spam_classifier_rejects_high_probability_message(self) -> None:
        with patch.dict(
            os.environ,
            {"NOISE_SPAM_CLASSIFIER_ENABLED": "true", "NOISE_SPAM_THRESHOLD": "0.80"},
            clear=False,
        ), patch("common.noise._load_spam_classifier", return_value=_SpamFixture()):
            analysis = analyze_noise(
                "This is a sufficiently detailed message that the test classifier marks as spam."
            )
        self.assertEqual(analysis.reason, "spam_classifier")
        self.assertEqual(analysis.spam_probability, 0.95)

    def test_minhash_rejects_near_duplicate_text(self) -> None:
        noise._near_indexes.clear()
        noise._near_index_keys.clear()
        with patch.dict(
            os.environ,
            {
                "NOISE_NEAR_DUPLICATE_ENABLED": "true",
                "NOISE_NEAR_DUPLICATE_THRESHOLD": "0.75",
                "NOISE_NEAR_DUPLICATE_PERMUTATIONS": "128",
            },
            clear=False,
        ):
            self.assertFalse(
                noise._near_duplicate(
                    "telegram", "threat-feed", "first",
                    "ransomware group published a new victim list with sample files today",
                )
            )
            self.assertTrue(
                noise._near_duplicate(
                    "telegram", "threat-feed", "second",
                    "ransomware group published a new victim list with sample files now",
                )
            )


if __name__ == "__main__":
    unittest.main()
