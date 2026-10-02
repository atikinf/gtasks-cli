#!/usr/bin/env python3
"""Main entry point for the Google Tasks CLI."""

import sys
from functools import cache

from googleapiclient.errors import HttpError

from gtasks.cli import ui
from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.client.client_factory import build_client
from gtasks.defaults import CONFIG_FILE_PATH
from gtasks.utils.config import Config


def _report_http_error(e: HttpError) -> None:
    if e.resp.status == 404:
        ui.error(
            "Google Tasks couldn't find that list or task.",
            hint="It may have been deleted elsewhere. Run `gtasks lists`, then `gtasks use`.",
        )
    else:
        ui.error(f"Google Tasks API error ({e.resp.status}): {e.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Handlers call this only if they use the API, so `auth` and `config` never load
    # credentials. Cached so a handler that calls it more than once gets one client.
    get_client = cache(build_client)

    try:
        cfg = Config(CONFIG_FILE_PATH)
        args.func(args, get_client=get_client, cfg=cfg)
        return 0
    except (KeyboardInterrupt, EOFError):
        ui.error(Cancelled().message)
        return Cancelled().exit_code
    except CliError as e:
        ui.error(e.message, hint=e.hint)
        return e.exit_code
    except ExceptionGroup as eg:
        # Batch mutations (done/delete) collect one exception per failed task.
        for sub in eg.exceptions:
            if isinstance(sub, HttpError):
                _report_http_error(sub)
            else:
                ui.error(str(sub))
        return 1
    except HttpError as e:
        _report_http_error(e)
        return 1
    except Exception as e:
        ui.error(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
