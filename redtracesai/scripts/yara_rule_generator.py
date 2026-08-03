"""Generate compile-validated YARA rules from the RedTraces STIX store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.stix_store import DEFAULT_DATABASE_PATH
from common.yara_rule_generator import DEFAULT_OUTPUT_DIRECTORY, generate_yara_rules


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=DEFAULT_DATABASE_PATH, help="SQLite IOC store"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="YARA output directory",
    )
    arguments = parser.parse_args()
    result = generate_yara_rules(
        database_path=arguments.database,
        output_directory=arguments.output_dir,
    )
    print(
        json.dumps(
            {
                "path": str(result.path),
                "generated_rules": result.generated_rules,
                "discarded_rules": result.discarded_rules,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
