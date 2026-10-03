"""Push generated Sigma or YARA artifacts to a configured SIEM provider."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from common.siem_pusher import push_sigma_file, push_yara_rule
from common.stix_store import DEFAULT_DATABASE_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--type", choices=("sigma", "yara"), required=True)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    arguments = parser.parse_args()

    if arguments.type == "sigma":
        results = push_sigma_file(arguments.artifact, database_path=arguments.database)
    else:
        results = [push_yara_rule(arguments.artifact, database_path=arguments.database)]
    print(json.dumps([asdict(result) for result in results], indent=2))
    if any(result.status == "failure" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
