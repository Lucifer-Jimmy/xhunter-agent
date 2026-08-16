"""Minimal dependency-free CLI."""

import argparse
import json
from pathlib import Path

from xhunter.application.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xhunter")
    parser.add_argument("--config", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "doctor", help="validate configuration and show runtime policy"
    )
    arguments = parser.parse_args(argv)
    config = load_config(arguments.config)
    if arguments.command == "doctor":
        print(
            json.dumps(
                {
                    "sandbox_provider": config.sandbox_provider,
                    "allowed_targets": config.allowed_targets,
                    "blocked_targets": config.blocked_targets,
                    "trace_path": str(config.trace_path),
                    "local_sandbox_unsafe": config.sandbox_provider == "local",
                },
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
