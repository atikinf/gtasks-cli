#!/usr/bin/env python3
"""Main entry point for the Google Tasks CLI."""

import sys

from gtasks.cli.cli import build_parser
from gtasks.client.client_factory import build_client
from gtasks.defaults import CONFIG_FILE_PATH
from gtasks.utils.config import Config


def main(argv: list[str] | None = None) -> int:
    client = build_client()

    cfg_path = CONFIG_FILE_PATH
    cfg = Config(cfg_path)
    parser = build_parser(client, cfg)

    args = parser.parse_args(argv)

    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
