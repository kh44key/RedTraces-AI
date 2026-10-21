"""Tests for the optional relevance pilot and its fail-open behavior."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from common import relevance_ai


class _Vectorizer:
    def transform(self, _texts: list[str]) -> list[str]:
        return ["features"]


class _Classifier:
    def decision_function(self, _features: object) -> list[float]:
        return [0.4]


class RelevancePilotTest(unittest.TestCase):
    def test_missing_model_fails_open(self) -> None:
        with patch.dict(os.environ, {"CTI_RELEVANCE_MODEL_PATH": "missing-model.joblib"}):
            relevance_ai._load.cache_clear()
            result = relevance_ai.classify_relevance("A sufficiently long English threat report.")
        self.assertEqual(result["label"], "unavailable")

    def test_non_english_text_is_not_scored(self) -> None:
        with patch.object(relevance_ai, "model_status", return_value={"enabled": True, "available": True, "model": "pilot"}):
            result = relevance_ai.classify_relevance("Это достаточно длинный текст", "ru")
        self.assertEqual(result["label"], "not_evaluated")

    def test_loaded_model_returns_margin_not_probability(self) -> None:
        artifact = {
            "word_vectorizer": _Vectorizer(),
            "char_vectorizer": _Vectorizer(),
            "model": _Classifier(),
            "threshold": 0.1,
        }
        with patch.object(relevance_ai, "model_status", return_value={"enabled": True, "available": True, "model": "pilot"}), patch.object(relevance_ai, "_model_path", return_value=relevance_ai.DEFAULT_MODEL), patch.object(relevance_ai, "_load", return_value=artifact), patch.object(relevance_ai, "hstack", return_value=["features"]):
            result = relevance_ai.classify_relevance("A sufficiently long English threat report.")
        self.assertEqual(result["label"], "relevant")
        self.assertEqual(result["margin"], 0.4)
        self.assertNotIn("probability", result)


if __name__ == "__main__":
    unittest.main()
