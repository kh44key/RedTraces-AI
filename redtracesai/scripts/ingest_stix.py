"""Ingest a generated STIX 2.1 bundle into the persistent SQLite IOC store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.stix_store import DEFAULT_DATABASE_PATH, STIXStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to a STIX Bundle JSON file")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help="SQLite path (default: /output/stix_store.sqlite3)",
    )
    arguments = parser.parse_args()

    with STIXStore(arguments.database) as store:
        result = store.ingest_file(arguments.bundle)
    print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
