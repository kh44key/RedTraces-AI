"""Generate a validated STIX bundle from a JSON array of normalized IOC records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.stix_generator import DEFAULT_OUTPUT_DIRECTORY, save_stix_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing normalized IOC records")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Bundle directory (default: /output/stix_bundles)",
    )
    arguments = parser.parse_args()

    records = json.loads(arguments.input.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("Input must be a JSON array of normalized IOC records")
    path = save_stix_bundle(records, output_directory=arguments.output_dir)
    print(path)


if __name__ == "__main__":
    main()
