# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --dev                      # install deps (Python >= 3.14)
uv run gtasks/app.py tasks         # run the CLI from source
uv run pytest                      # run all tests
uv run pytest tests/client/test_api_client.py::TestGetTasklists  # single class/test
uv run pytest --cov=gtasks         # coverage (pytest-cov installed)
uv run ruff check .                # lint (CI gate)
uv run ty check                    # type check (available, not in CI)
```

CI (`.github/workflows`) runs `ruff check .` then `pytest` on pushes/PRs to `master`.

## Architecture

**Parser-per-command, dependencies resolved after parsing.** Each command is a module in
`gtasks/cli/parsers/<name>_parser.py` exposing a pair:

- `cmd_<name>(args, get_client, cfg)` — the handler (all three params present even if a given
  handler ignores one or two of them, e.g. `cmd_auth`, `cmd_config`)
- `add_subparser_<name>(subparsers)` — registers the argparse subparser and points
  `set_defaults(func=cmd_<name>)` at the *unbound* handler; no client/cfg at parse time

`cli/cli.py:build_parser` wires every subparser and is pure structure — it never touches a client
or config. `app.py:main` calls `parser.parse_args(argv)` first, only then builds `cfg`, and
dispatches with `args.func(args, get_client=get_client, cfg=cfg)`. `get_client` (typed
`client/protocol.py:ClientProvider`) builds the client via `client_factory.build_client` once per
freshness per run, and handlers that use the API call it on their first line; `auth` and `config`
never do. So the client — and with it credential loading and the OAuth flow — is built only by
commands that need it: never for `--help` or invalid invocations, and never for `auth` (which
creates those credentials) or `config`. Tests pass `lambda **_: mock_client`.
To add a command: write the module pair, then register it in `build_parser`. Bare `gtasks` is
handled by a top-level `set_defaults` pointing at `cmd_list_tasks` with `limit=10`.

**Which list a command acts on.** Every list-scoped handler calls
`title_id_resolution.resolve_target_tasklist`, whose precedence is: `-l/--list` flag >
`$GTASKS_LIST` > the active list (`gtasks use`, stored by ID in config) > the account's
`@default` list. A pre-ID `default_tasklist = <title>` config entry is migrated to the ID keys on
first use. Register `-l` with `add_tasklist_option` — it's on the top-level parser too, so the
subparser copies default to `argparse.SUPPRESS` to avoid clobbering `gtasks -l X done 1`. Any
option accepted before or after the subcommand goes through `cli_utils.add_shared_option`.

**Title→ID resolution.** Users address tasks and lists by title, never by API ID. All of it lives
in `cli/title_id_resolution.py`:

- Matching is CLI policy, not a client method: `match_title` (case-insensitive, exact) filters
  what `get_tasklists()` / `get_tasks()` return; `_choose_one` then prompts only when titles
  collide, and no match raises `CliError`. Both are shared by lists and tasks.
- Lists: `find_tasklist(client, title)` = `match_title` over `get_tasklists()` → `choose_tasklist`.
- `resolve_tasks_from_inputs` accepts titles or 1-based display numbers. Numbers
  resolve against the last listing shown for that list (`utils/listing_state.py`, written by
  `cmd_list_tasks`), so `done 3` hits the task the user saw even if the list changed since; rows
  are marked consumed after `done`/`delete`. With no recorded listing numbers index the
  needsAction list; titles always match against it (open tasks only), fetched once per call.
  Any unresolvable input raises before a batch is sent.

**Output and errors.** All terminal output goes through `cli/ui.py` (rich, one `THEME` of semantic
styles); handlers never `print`. User strings are wrapped in `Text`, never interpolated into rich
markup. Handlers raise `cli/errors.py:CliError(message, hint=, exit_code=)` instead of printing
and calling `sys.exit`; `app.main` renders it (plus `ExceptionGroup`, `HttpError`, Ctrl-C) to
stderr. Errors bubble up untouched and are mapped to messages only there. Signed-out states all
end in a `gtasks auth` hint via `_report_signed_out`: `SignInRequiredError` (raised by
`client_factory` when there's no usable token and no `credentials.json`), a mid-request
`RefreshError`, and HTTP 401. The client layer raises its own exception and never imports from
`cli/`. A failed token refresh falls back to a fresh sign-in, so `gtasks auth` can always
replace a revoked token.
`tests/conftest.py` installs plain, uncoloured consoles (via `ui.use_consoles`) and clears
`$GTASKS_LIST` for every test, so output assertions hold under `FORCE_COLOR`/`-s`.

**Cache.** Unless `cache = off`, `build_client` wraps `ApiClient` in
`client/caching_client.py:CachingClient`, backed by `client/cache_store.py` (plain JSON, no Google
imports, so shell completion can read it without signing in). Reads of task lists and of a
list's open tasks (only the exact query the CLI makes; other filters pass through) are served
from disk for 30 minutes. The rule that keeps staleness harmless: **reads that decide which task a
write hits are fresh** — `done`/`delete` call `get_client(fresh=True)`, which never serves cached
data but still stores what it fetches; `--refresh` makes any command fresh (register it with
`cli_utils.add_refresh_option` on every subcommand that uses the API). Task writes refetch
the list concurrently on a second client (`make_refresher`: its own httplib2 connection, which
isn't thread-safe to share, with a timeout) and merge the write's result into that copy;
anything not safely mergeable drops the list's file instead. `tasks_fetched_at` (the protocol's
one non-API method) lets `tasks` show "cached 12m ago". The listing snapshot (`state.json`) is
deliberately separate: it freezes what was shown so numbers never shift, while the cache tracks
what's current.

**Batch mutations.** `done` and `delete` accept multiple tasks and issue one
`new_batch_http_request`; partial failures are collected and raised as an `ExceptionGroup`.

**Layers.** `cli/` (argparse + presentation) → `client/api_client.py` (thin Google Tasks wrapper,
handles pagination in `_pagination_loop`) → `client/client_factory.py` (OAuth, builds the
`TasksResource`). `ApiClient` is constructed from a `TasksResource`, which is what makes it
trivially mockable in tests. `ApiClient` does mechanics only — snake_case → API names, pagination,
batching — and no user-facing policy (matching, filtering): each method maps to one Tasks API
operation (or a batch of one), named after the resource (`update_task`, `update_tasklist`).
Unset optionals go through `_given()` so they're left out of the request: a `None` body field
would be sent as JSON null, which a patch treats as "clear".

**Contract layer.** `client/protocol.py` defines `TasksClient`, a structural `Protocol` mirroring
`ApiClient`'s full public surface (14 methods, grouped by resource — tasklist reads/writes, task
reads/writes, batch/bulk task mutations) plus `tasks_fetched_at` (cache metadata; `ApiClient`
returns `None`), the `Status` enum used by `update_task`, and `ClientProvider`, so new
client code and new CLI commands can be typed against the contract without waiting on a consumer
to exist. The CLI (`cmd_<name>` handlers in `cli/parsers/` and `title_id_resolution.py`) currently
consumes 6 of these (`get_tasklists`, `get_tasklist`, `get_tasks`, `add_task`, `complete_tasks`,
`delete_tasks`); the remaining 8 close the gap with the Tasks API v1 surface and aren't yet wired
into any CLI command. Either way, the CLI types its client as `TasksClient` (handlers via
`get_client: ClientProvider`), imported under `TYPE_CHECKING` since it's never instantiated there
— only `client_factory.build_client()` constructs a real `ApiClient` (or `CachingClient`) and is
declared to return `TasksClient`. `ApiClient` needs no inheritance or declaration to satisfy the
contract — it conforms structurally, which is also why a bare `Mock()` satisfies it in tests with
no setup. This keeps CLI code decoupled from the concrete implementation: `CachingClient`
satisfies the same contract, so swapping it in needed no handler changes beyond asking for fresh
reads.

## On-disk state (`~/.config/gtasks-cli/`, see `defaults.py`)

- `config.toml` — despite the extension this is **INI**, written by `ConfigParser` via
  `utils/config.py:Config`. Settings are declared in the `ConfigKey` enum; adding a key means
  adding an enum member plus a description in `config_parser.py:_DESCRIPTIONS` (and its allowed
  values in `_ALLOWED_VALUES`, if restricted). The active list lives here as
  `active_tasklist_id` + `active_tasklist_title` (display cache, refreshed by `lists`); `config`
  refuses to set those (`_MANAGED_BY`) — only `use` writes them. `cache` is `on` (default) or
  `off`.
- `state.json` — app-managed, not configuration: the last task listing shown (see above). Located
  beside `config.toml` via `ListingState.beside(cfg)`, so tests using a tmp config stay isolated.
- `credentials.json` — user-supplied OAuth client secrets from Google Cloud Console.
- `token.pickle` — pickled `Credentials`, refreshed automatically when expired.

The cache lives apart, in `$XDG_CACHE_HOME/gtasks-cli` (default `~/.cache/gtasks-cli`, see
`defaults.CACHE_DIR`), one directory per signed-in account (`cache_store.account_key`, a hash of
the client ID and refresh token, so accounts never see each other's data; `current` names the
active one). Inside: `tasklists.json` (all lists plus what `@default` resolved to) and
`lists/<sha256(id)>.json` (one list's open tasks). Every file carries a semver `schema`: readers
accept the same MAJOR and treat anything else as a miss — bump MAJOR for shape/meaning changes,
MINOR for added fields. Unreadable or corrupt files are misses and failed writes are skipped, so
the cache can never break a command. `gtasks auth` clears it.

## Conventions

- Google API types (`Task`, `TaskList`, `TasksResource`) come from `google-api-python-client-stubs`
  and are imported under `if TYPE_CHECKING:` only — they do not exist at runtime.
- `TasksClient` (`client/protocol.py`) is a `Protocol`, not an ABC — deliberately, so plain
  `Mock()`/`MagicMock()` test doubles satisfy it with no `spec=` or subclassing.
- ruff: line-length 100, rules `E,F,I,W`, `gtasks` as first-party for isort.
- Tests: `test_<fn>_GIVEN_<condition>_THEN_<result>` naming, grouped in `Test*` classes, with a
  `MagicMock` service fixture per module. `tests/conftest.py` holds only the autouse
  output/env isolation fixture; other fixtures stay per-module.
