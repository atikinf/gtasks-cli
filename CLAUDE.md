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

**Title→ID resolution.** Users address tasks and lists by title, never by API ID:

- `ApiClient.resolve_tasklist_from_title` (case-insensitive) → `cli_utils.prompt_choose_tasklist_id`
  disambiguates duplicate titles interactively → id.
- `cli_utils.resolve_tasks_from_inputs` accepts either 1-based *display* indices (matching the
  numbering `print_tasks` emits; the needsAction list is fetched lazily on the first digit) or
  titles, and returns full task objects.

**Batch mutations.** `done` and `delete` accept multiple tasks and issue one
`new_batch_http_request`; partial failures are collected and raised as an `ExceptionGroup`.

**Layers.** `cli/` (argparse + presentation) → `client/api_client.py` (thin Google Tasks wrapper,
handles pagination in `_pagination_loop`) → `client/client_factory.py` (OAuth, builds the
`TasksResource`). `ApiClient` is constructed from a `TasksResource`, which is what makes it
trivially mockable in tests.

## On-disk state (`~/.config/gtasks-cli/`, see `defaults.py`)

- `config.toml` — despite the extension this is **INI**, written by `ConfigParser` via
  `utils/config.py:Config`. Settings are declared in the `ConfigKey` enum; adding a key means
  adding an enum member plus a description in `config_parser.py:_DESCRIPTIONS`.
- `credentials.json` — user-supplied OAuth client secrets from Google Cloud Console.
- `token.pickle` — pickled `Credentials`, refreshed automatically when expired.

## Conventions

- Google API types (`Task`, `TaskList`, `TasksResource`) come from `google-api-python-client-stubs`
  and are imported under `if TYPE_CHECKING:` only — they do not exist at runtime.
- ruff: line-length 100, rules `E,F,I,W`, `gtasks` as first-party for isort.
- Tests: `test_<fn>_GIVEN_<condition>_THEN_<result>` naming, grouped in `Test*` classes, with a
  `MagicMock` service fixture per module. There is no `conftest.py`.
