"""Generate batched Sigma rules from the persistent RedTraces STIX store."""

from __future__ import annotations

import argparse
from pathlib import Path

from common.sigma_rule_generator import DEFAULT_OUTPUT_DIRECTORY, generate_sigma_rules
from common.stix_store import DEFAULT_DATABASE_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=DEFAULT_DATABASE_PATH, help="SQLite IOC store"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Sigma output directory",
    )
    arguments = parser.parse_args()
    print(
        generate_sigma_rules(
            database_path=arguments.database,
            output_directory=arguments.output_dir,
        )
    )


if __name__ == "__main__":
    main()
