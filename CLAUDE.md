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

- `cmd_<name>(args, client, cfg)` — the handler (all three params present even if a given
  handler ignores one or two of them, e.g. `cmd_auth`, `cmd_config`)
- `add_subparser_<name>(subparsers)` — registers the argparse subparser and points
  `set_defaults(func=cmd_<name>)` at the *unbound* handler; no client/cfg at parse time

`cli/cli.py:build_parser` wires every subparser and is pure structure — it never touches a client
or config. `app.py:main` calls `parser.parse_args(argv)` first, only then builds `cfg` and `client`,
and dispatches with `args.func(args, client=client, cfg=cfg)`. This is deliberate: it keeps
`--help` and invalid invocations from ever loading credentials or launching the OAuth flow. To add
a command: write the module pair, then register it in `build_parser`. Bare `gtasks` is handled by
a top-level `set_defaults` pointing at `cmd_list_tasks` with `limit=10`.

**Which list a command acts on.** Every list-scoped handler calls
`tasklist_resolution.resolve_target_tasklist`, whose precedence is: `-l/--list` flag >
`$GTASKS_LIST` > the active list (`gtasks use`, stored by ID in config) > the account's
`@default` list. A pre-ID `default_tasklist = <title>` config entry is migrated to the ID keys on
first use. Register `-l` with `add_tasklist_option` — it's on the top-level parser too, so the
subparser copies default to `argparse.SUPPRESS` to avoid clobbering `gtasks -l X done 1`.

**Title→ID resolution.** Users address tasks and lists by title, never by API ID:

- `ApiClient.resolve_tasklist_from_title` (case-insensitive) → `tasklist_resolution.choose_tasklist`
  prompts only when titles collide; no match raises `CliError`.
- `task_resolution.resolve_tasks_from_inputs` accepts titles or 1-based display numbers. Numbers
  resolve against the last listing shown for that list (`utils/listing_state.py`, written by
  `cmd_list_tasks`), so `done 3` hits the task the user saw even if the list changed since; rows
  are marked consumed after `done`/`delete`. With no recorded listing it fetches the needsAction
  list. Any unresolvable input raises before a batch is sent.

**Output and errors.** All terminal output goes through `cli/ui.py` (rich, one `THEME` of semantic
styles); handlers never `print`. User strings are wrapped in `Text`, never interpolated into rich
markup. Handlers raise `cli/errors.py:CliError(message, hint=, exit_code=)` instead of printing
and calling `sys.exit`; `app.main` renders it (plus `ExceptionGroup`, `HttpError`, Ctrl-C) to
stderr. `tests/conftest.py` installs plain, uncoloured consoles (via `ui.use_consoles`) and clears
`$GTASKS_LIST` for every test, so output assertions hold under `FORCE_COLOR`/`-s`.

**Batch mutations.** `done` and `delete` accept multiple tasks and issue one
`new_batch_http_request`; partial failures are collected and raised as an `ExceptionGroup`.

**Layers.** `cli/` (argparse + presentation) → `client/api_client.py` (thin Google Tasks wrapper,
handles pagination in `_pagination_loop`) → `client/client_factory.py` (OAuth, builds the
`TasksResource`). `ApiClient` is constructed from a `TasksResource`, which is what makes it
trivially mockable in tests.

**Contract layer.** `client/protocol.py` defines `TasksClient`, a structural `Protocol` mirroring
`ApiClient`'s full public surface (16 methods, grouped by resource — tasklist reads/writes, task
reads/writes, batch/bulk task mutations — then the two `resolve_*_from_title` lookups), so new
client code and new CLI commands can be typed against the contract without waiting on a consumer
to exist. The CLI (`cmd_<name>` handlers in `cli/parsers/`, `task_resolution.py`,
`tasklist_resolution.py`) currently consumes 8 of these (`get_tasklists`, `get_tasklist`,
`resolve_tasklist_from_title`, `resolve_task_from_title`, `get_tasks`, `add_task`,
`complete_tasks`, `delete_tasks`); the remaining 8 close the gap with the Tasks API v1 surface and
aren't yet wired into any CLI command. Either way, the CLI types its `client` params as
`TasksClient`, imported under `TYPE_CHECKING` since it's never instantiated there — only
`client_factory.build_client()` constructs a real `ApiClient` and is declared to return
`TasksClient`. `ApiClient` needs no inheritance or declaration to satisfy the contract — it
conforms structurally, which is also why a bare `Mock()` satisfies it in tests with no setup. This
keeps CLI code decoupled from the concrete implementation so a future swappable implementation
(e.g. a config-toggled caching variant) can satisfy the same contract with no consumer changes.

## On-disk state (`~/.config/gtasks-cli/`, see `defaults.py`)

- `config.toml` — despite the extension this is **INI**, written by `ConfigParser` via
  `utils/config.py:Config`. Settings are declared in the `ConfigKey` enum; adding a key means
  adding an enum member plus a description in `config_parser.py:_DESCRIPTIONS`. The active list
  lives here as `active_tasklist_id` + `active_tasklist_title` (display cache, refreshed by
  `lists`); `config` refuses to set those (`_MANAGED_BY`) — only `use` writes them.
- `state.json` — app-managed, not configuration: the last task listing shown (see above). Located
  beside `config.toml` via `ListingState.beside(cfg)`, so tests using a tmp config stay isolated.
- `credentials.json` — user-supplied OAuth client secrets from Google Cloud Console.
- `token.pickle` — pickled `Credentials`, refreshed automatically when expired.

## Conventions

- Google API types (`Task`, `TaskList`, `TasksResource`) come from `google-api-python-client-stubs`
  and are imported under `if TYPE_CHECKING:` only — they do not exist at runtime.
- `TasksClient` (`client/protocol.py`) is a `Protocol`, not an ABC — deliberately, so plain
  `Mock()`/`MagicMock()` test doubles satisfy it with no `spec=` or subclassing.
- ruff: line-length 100, rules `E,F,I,W`, `gtasks` as first-party for isort.
- Tests: `test_<fn>_GIVEN_<condition>_THEN_<result>` naming, grouped in `Test*` classes, with a
  `MagicMock` service fixture per module. `tests/conftest.py` holds only the autouse
  output/env isolation fixture; other fixtures stay per-module.
