"""Local English CTI relevance pilot (linear SVM with word/character TF-IDF).

This is a review aid, not a maliciousness verdict. The held-out evaluation is
from formal CTI reports, so its metrics must not be presented as Telegram or
dark-forum performance.
"""

from __future__ import annotations

import json
import os
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
from scipy.sparse import hstack


DEFAULT_MODEL = Path(__file__).resolve().parents[1] / "ml" / "outputs" / "relevance-cpu-2026-10-12" / "model.joblib"
DEFAULT_EVALUATION = DEFAULT_MODEL.with_name("evaluation.json")


def _model_path() -> Path:
    return Path(os.getenv("CTI_RELEVANCE_MODEL_PATH", str(DEFAULT_MODEL))).expanduser()


@lru_cache(maxsize=2)
def _load(path: str) -> dict[str, Any] | None:
    model_path = Path(path)
    if not model_path.is_file():
        return None
    try:
        artifact = joblib.load(model_path)
        if not all(key in artifact for key in ("model", "word_vectorizer", "char_vectorizer", "threshold")):
            return None
        return artifact
    except Exception:
        # A missing or incompatible artifact must never interrupt collection.
        return None


def model_status() -> dict[str, Any]:
    path = _model_path()
    artifact = _load(str(path))
    result: dict[str, Any] = {
        "enabled": os.getenv("CTI_RELEVANCE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"},
        "available": artifact is not None,
        "model": "TF-IDF word+character features + LinearSVC",
        "scope": "English text only; research triage aid",
        "auto_filter": os.getenv("CTI_RELEVANCE_FILTER_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
        "evaluation_domain": "SMAH-CTI formal report sentences; not Telegram/dark-forum conversations",
        "test_accuracy": 0.7684,
        "test_relevant_precision": 0.6980,
        "test_relevant_recall": 0.6114,
        "test_macro_f1": 0.7392,
        "test_rows": 2431,
        "test_split_used_for_threshold": False,
    }
    evaluation_path = Path(os.getenv("CTI_RELEVANCE_EVALUATION_PATH", str(DEFAULT_EVALUATION)))
    try:
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        score = evaluation["test"]
        result.update({
            "test_accuracy": score["accuracy"],
            "test_relevant_precision": score["precision_relevant"],
            "test_relevant_recall": score["recall_relevant"],
            "test_macro_f1": score["macro_f1"],
            "test_rows": evaluation["rows"]["test"],
        "test_split_used_for_threshold": False,
        })
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if artifact is not None:
        result["threshold"] = float(artifact["threshold"])
        result["features"] = artifact.get("features", "word_char")
    if not result["enabled"]:
        result["available"] = False
        result["reason"] = "disabled by CTI_RELEVANCE_ENABLED"
    elif artifact is None:
        result["reason"] = "model artifact missing or could not be loaded"
    return result


def classify_relevance(text: str | None, language: str = "en") -> dict[str, Any]:
    """Return a validation-threshold label and raw SVM margin when applicable."""
    status = model_status()
    if not status["enabled"] or not status["available"]:
        return {"label": "unavailable", "margin": None, "model": status["model"]}
    if language != "en":
        return {"label": "not_evaluated", "margin": None, "model": status["model"]}
    normalized = unicodedata.normalize("NFKC", text or "").strip()
    if len(normalized) < 12:
        return {"label": "not_evaluated", "margin": None, "model": status["model"]}
    artifact = _load(str(_model_path()))
    if artifact is None:
        return {"label": "unavailable", "margin": None, "model": status["model"]}
    try:
        word = artifact["word_vectorizer"].transform([normalized])
        char = artifact["char_vectorizer"].transform([normalized])
        margin = float(artifact["model"].decision_function(hstack([word, char], format="csr"))[0])
        threshold = float(artifact["threshold"])
        return {
            "label": "relevant" if margin >= threshold else "low_relevance",
            "margin": margin,
            "threshold": threshold,
            "model": "redtraces-english-linear-svm-pilot-v1",
        }
    except Exception:
        return {"label": "unavailable", "margin": None, "model": status["model"]}
