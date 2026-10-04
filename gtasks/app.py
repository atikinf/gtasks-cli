#!/usr/bin/env python3
"""Main entry point for the Google Tasks CLI."""

import sys
from functools import cache
from typing import TYPE_CHECKING

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from gtasks.cli import ui
from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.client.client_factory import SignInRequiredError, build_client
from gtasks.defaults import CACHE_DIR, CONFIG_FILE_PATH
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient


def _report_signed_out(e: SignInRequiredError | RefreshError | HttpError) -> None:
    """Every way of being signed out ends in the same pointer to `gtasks auth`."""
    if isinstance(e, SignInRequiredError):
        message = "You're not signed in to Google Tasks."
    else:
        message = "Your Google sign-in has expired or was revoked."
    ui.error(message, hint="Run `gtasks auth` to sign in.")


def _report_http_error(e: HttpError) -> None:
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = Config(CONFIG_FILE_PATH)
        cache_dir = None if cfg.get(ConfigKey.CACHE) == "off" else CACHE_DIR
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
            if isinstance(sub, HttpError):
                _report_http_error(sub)
            else:
                ui.error(str(sub))
        return 1
    except (SignInRequiredError, RefreshError) as e:
        # Raised when the client is built, or mid-request if the sign-in was revoked.
        _report_signed_out(e)
        return 1
    except HttpError as e:
        _report_http_error(e)
        return 1
    except Exception as e:
        ui.error(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
