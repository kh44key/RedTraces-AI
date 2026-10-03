"""Create a balanced CTI-versus-spam CSV for Layer 2 pipeline testing.

The output is explicitly for testing only. It combines MITRE ATT&CK text as
the CTI class with UCI SMS Spam Collection examples as the spam class; it is
not representative enough to enable on live collection feeds.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def attack_texts(bundle_path: Path) -> list[str]:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    texts: list[str] = []
    for item in bundle.get("objects", []):
        if item.get("revoked") or item.get("x_mitre_deprecated"):
            continue
        if item.get("type") not in {
            "attack-pattern",
            "campaign",
            "intrusion-set",
            "malware",
            "tool",
        }:
            continue
        description = str(item.get("description", "")).strip()
        name = str(item.get("name", "")).strip()
        text = f"{name}. {description}".strip()
        if len(text) >= 40:
            texts.append(text)
    return texts


def spam_texts(collection_path: Path) -> list[str]:
    texts: list[str] = []
    for line in collection_path.read_text(encoding="utf-8", errors="replace").splitlines():
        label, separator, text = line.partition("\t")
        if separator and label.strip().lower() == "spam" and text.strip():
            texts.append(text.strip())
    return texts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("attack_json", type=Path)
    parser.add_argument("sms_collection", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/testing/layer2_test.csv"))
    parser.add_argument("--per-class", type=int, default=700)
    args = parser.parse_args()

    cti = attack_texts(args.attack_json)[: args.per_class]
    spam = spam_texts(args.sms_collection)[: args.per_class]
    if len(cti) < 20 or len(spam) < 20:
        raise SystemExit("Both sources must provide at least 20 usable examples.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["text", "label"])
        writer.writeheader()
        for text in cti:
            writer.writerow({"text": text, "label": "cti"})
        for text in spam:
            writer.writerow({"text": text, "label": "spam"})
    print(f"Wrote {len(cti)} CTI and {len(spam)} spam rows to {args.output}")


if __name__ == "__main__":
    main()
