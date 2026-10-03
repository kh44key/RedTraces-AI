"""Train the optional Layer 2 logistic-regression spam classifier from CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/spam_classifier.joblib"))
    args = parser.parse_args()

    with args.input_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    texts = [row.get("text", "").strip() for row in rows if row.get("text", "").strip()]
    labels = [row["label"].strip().lower() for row in rows if row.get("text", "").strip()]
    if len(texts) < 20 or set(labels) != {"cti", "spam"}:
        raise SystemExit("CSV needs at least 20 rows and both labels: cti, spam")

    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )
    model.fit(texts, [1 if label == "spam" else 0 for label in labels])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.output)
    print(f"Saved model to {args.output}")


if __name__ == "__main__":
    main()
