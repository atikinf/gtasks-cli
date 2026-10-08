#!/usr/bin/env python3
"""Main entry point for the Google Tasks CLI."""

import os
import sys
from functools import cache
from typing import TYPE_CHECKING

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.client.client_factory import SignInRequiredError, build_client
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from googleapiclient.errors import HttpError

    from gtasks.client.protocol import TasksClient


def _report_signed_out(e: Exception) -> None:
    """Every way of being signed out ends in the same pointer to `gtasks auth`."""
    if isinstance(e, SignInRequiredError):
        message = "You're not signed in to Google Tasks."
    else:
        message = "Your Google sign-in has expired or was revoked."
    ui.error(message, hint="Run `gtasks auth` to sign in.")


def _report_http_error(e: "HttpError") -> None:
    if e.resp.status == 401:
        _report_signed_out(e)
    elif e.resp.status == 404:
        ui.error(
            "Google Tasks couldn't find that list or task.",
            hint="It may have been deleted elsewhere. Run `gtasks lists --refresh`, then "
            "`gtasks use`.",
        )
    else:
        ui.error(f"Google Tasks API error ({e.resp.status}): {e.reason}")


def _report_error(e: Exception) -> None:
    """Explain an error that isn't a CliError.

    Google's error types are imported here rather than at module level: only a failing
    command pays for them, and a command served from the cache never imports them at all.
    """
    from google.auth.exceptions import RefreshError
    from googleapiclient.errors import HttpError

    if isinstance(e, (SignInRequiredError, RefreshError)):
        # Raised when the client is built, or mid-request if the sign-in was revoked.
        _report_signed_out(e)
    elif isinstance(e, HttpError):
        _report_http_error(e)
    else:
        ui.error(str(e))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if "_ARGCOMPLETE" in os.environ:
        # The shell is asking for Tab completions: answer from local data and exit, before
        # anything else is loaded or built.
        from gtasks.cli.completion import complete

        complete(parser)
        return 0  # only reached if completion couldn't run; never fall through to a command
    args = parser.parse_args(argv)

    try:
        cfg = Config.default()
        cache_dir = None if cfg.get(ConfigKey.CACHE) == "off" else defaults.CACHE_DIR
        force_fresh = getattr(args, "refresh", False)

        @cache
        def build(fresh: bool) -> "TasksClient":
            return build_client(fresh=fresh, cache_dir=cache_dir)

        # Injected into handlers, which call it only if they use the API, so `auth` and
        # `config` never load credentials. One client per freshness per run.
        def get_client(*, fresh: bool = False) -> "TasksClient":
            return build(fresh or force_fresh)

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
            _report_error(sub)
        return 1
    except Exception as e:
        _report_error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
