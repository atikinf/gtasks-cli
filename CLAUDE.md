# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --dev                      # install deps (Python >= 3.14)
uv run gtasks/app.py tasks         # run the CLI from source
uv run gtasks-mcp                  # run the MCP server (stdio) from source
uv run pytest                      # run all tests
uv run pytest tests/client/test_api_client.py::TestGetTasklists  # single class/test
uv run pytest --cov=gtasks         # coverage (pytest-cov installed)
uv run ruff check .                # lint (CI gate)
uv run ty check gtasks             # type check the package (CI gate; tests not checked)
```

CI (`.github/workflows`) runs `ruff check .`, `ty check gtasks`, then `pytest` on pushes/PRs to `master`.

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
handled by a top-level `set_defaults` pointing at `cmd_tasks` with
`limit=tasks_parser.DEFAULT_LIMIT` (10). The listing itself is `tasks_parser.show_tasks` (fetch,
render, record the listing for numbers), shared by `tasks`, bare `gtasks` and `use`, which shows
the newly active list right after switching (cached like bare `gtasks`; `--refresh` for fresh).
Likewise `lists_parser.show_tasklists` (fetch all, keep the active list's stored title current
on renames, apply `limit` with a "more not shown" note, render) serves `lists` and the `use`
picker, and `cli/task_actions.act_on_tasks` is the shared `done`/`delete` flow: fresh client,
resolve inputs, optional confirm, act, retire listing numbers, report.
Display order is `cli/task_order.py:display_order` (pure): the app's manual order (`position`,
relative to siblings) with subtasks right under their parent; the API itself returns most
recently updated first. So `show_tasks` fetches the whole list and applies `limit` after
ordering, number fallback in `resolve_tasks_from_inputs` uses the same order, and `ui.render_tasks`
marks a subtask `└` when its parent is shown. The cache keeps API order; ordering is display-only.

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
  `cmd_tasks`), so `done 3` hits the task the user saw even if the list changed since; rows
  are marked consumed after `done`/`delete`. With no recorded listing numbers index the
  needsAction list; titles always match against it (open tasks only), fetched once per call.
  Any unresolvable input raises before a batch is sent.

**Partial titles and Tab completion.** `cli/title_matching.py` is the one matcher (pure, no I/O)
for both: titles compare case- and whitespace-insensitively; an exact title beats any partial
(substring) match; with neither, `difflib` suggestions feed a "Did you mean" hint. Enter-matching
(`title_id_resolution._choose_one`): one match acts, several open the numbered picker, none
errors, with suggestions prepended to the usual hint (kept for lists: it's the stale-cache fix).
`resolve_tasks_from_inputs` returns `ResolvedTasks(tasks, partial)`, where `partial` holds tasks a
fragment selected on its own (not ones picked from the numbered list); `delete` confirms those
(`prompt_yes_no`, skip with `-y`), `done` doesn't; legacy-config migration is exact-only.
Tab completion (`cli/completion.py`, argcomplete) runs only when the shell sets `_ARGCOMPLETE` —
`app.main` answers and exits before parsing, and never falls through to a command. Completers
read fresh cache data only, via `CacheStore.for_current_account` (no credentials, no Google
imports), match title prefixes (`complete_titles`), never raise, and are attached with
`completion.attach(action, fn)`. `complete_tasks` returns `{title: due label}`: zsh and fish
show descriptions, bash ignores them. `gtasks completion <shell>` prints argcomplete's snippet;
for zsh it appends a `matcher-list` zstyle scoped to gtasks so zsh doesn't drop candidates whose
case differs from what was typed (zsh filters case-sensitively by default).

**Output and errors.** All terminal output goes through `cli/ui.py` (rich, one `THEME` of semantic
styles); handlers never `print`. User strings are wrapped in `Text`, never interpolated into rich
markup. Show a task's or list's title with `ui.display_title` (Google sends
untitled items with an empty title, so a `.get` default never applies). Handlers raise `cli/errors.py:CliError(message, hint=, exit_code=)` instead of printing
and calling `sys.exit`; `app.main` renders it (plus `ExceptionGroup`, `HttpError`, Ctrl-C) to
stderr. Errors bubble up untouched and are mapped to messages only there. Signed-out states all
end in a `gtasks auth` hint via `_report_signed_out`: `SignInRequiredError` (raised by
`client_factory` when there's no usable token and no `credentials.json`), a mid-request
`RefreshError`, and HTTP 401. The client layer raises its own exception and never imports from
`cli/`. A failed token refresh falls back to a fresh sign-in, so `gtasks auth` can always
replace a revoked token.
`tests/conftest.py` installs plain, uncoloured consoles (via `ui.use_consoles`), clears
`$GTASKS_LIST` and points `defaults.CACHE_DIR` at a tmp dir for every test, so output assertions
hold under `FORCE_COLOR`/`-s` and nothing touches the real `~/.cache`.

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
anything not safely mergeable drops the list's file instead. Completing or deleting a task also removes
its subtasks from the cached copy (`_without_subtrees`), as Google Tasks does (checked live). `tasks_cache_state` and
`tasklists_cache_state` (the protocol's only non-API methods; `ApiClient` returns `None`) return a
`CacheState(from_cache, fetched_at)` so `tasks`, `lists` and the `use` picker can say
"cache refreshed" (fetched live and saved), "cached 12m ago" (served from it), or nothing (no
cache involved). Store writes return the recorded fetch time or `None`, so a failed save is
never reported as "refreshed". The listing snapshot (`listing.json`) is deliberately separate: it
freezes what was shown so numbers never shift, while the cache tracks what's current.

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

**MCP server.** `gtasks/mcp_server/server.py` (`gtasks-mcp`, the optional `mcp` extra, SDK v2
`MCPServer`) is a sibling of `cli/` that depends on `client/` only: tools take and return API
IDs, so none of the title matching, listing numbers or prompts apply. stdout is the protocol
stream, so it never uses `ui`, and builds clients with `build_client(allow_sign_in=False)`
(signed out → `SignInRequiredError`, never the browser flow). Sync tools run on worker threads,
so every call builds its own client, under a lock. Client errors become `ToolError`s via
`_client_errors` (anything else reaches the model as a bare "Error executing tool"). Dates in
and out are strict `YYYY-MM-DD`; `list_tasks` filters client-side so the open-tasks cache still
serves it, and caps results across lists (`limit`, oldest/earliest-due first when filtering,
per-list `total`, shortened notes; `get_task` has them in full) since a full account runs to
~100 KB. `build_server(get_client)` takes the provider, so tests pass `lambda **_: mock` and
drive tools through `server.call_tool` (anyio). `test_startup.py` keeps `mcp`/`pydantic` out of
the CLI's imports.

**Contract layer.** `client/protocol.py` defines `TasksClient`, a structural `Protocol` mirroring
`ApiClient`'s full public surface (14 methods, grouped by resource — tasklist reads/writes, task
reads/writes, batch/bulk task mutations) plus `tasks_cache_state`/`tasklists_cache_state` (cache
metadata, as `CacheState`; `ApiClient` returns `None`), the `Status` enum used by `update_task`, and
`ClientProvider`, so new client code and new CLI commands can be typed against the contract
without waiting on a consumer to exist. The CLI (`cmd_<name>` handlers in `cli/parsers/` and `title_id_resolution.py`) currently
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

## On-disk state (`~/.config/gtasks-cli/` and `~/.cache/gtasks-cli/`, see `defaults.py`)

- `config.toml` — despite the extension this is **INI**, written by `ConfigParser` via
  `utils/config.py:Config`. Settings are declared in the `ConfigKey` enum; adding a key means
  adding an enum member plus a description in `config_parser.py:_DESCRIPTIONS` (and its allowed
  values in `_ALLOWED_VALUES`, if restricted). The active list lives here as
  `active_tasklist_id` + `active_tasklist_title` (display cache, refreshed by `lists`); `config`
  refuses to set those (`_MANAGED_BY`) — only `use` writes them. `cache` is `on` (default) or
  `off`.
- `credentials.json` — user-supplied OAuth client secrets from Google Cloud Console.
- `token.json` — the saved sign-in in Google's authorized-user format (`Credentials.to_json()`),
  written atomically and 0600, refreshed automatically when expired. Not a pickle: a pickle
  names google-auth internals, so it can fail to load under another google-auth version (an
  installed gtasks vs. a checkout). A legacy `token.pickle` is migrated on first read and
  removed; one that won't load is left alone and gtasks signs in afresh. An unreadable
  `token.json` likewise reads as signed out.

Everything gtasks manages itself (disposable, never configuration) lives apart, in
`$XDG_CACHE_HOME/gtasks-cli` (default `~/.cache/gtasks-cli`, see `defaults.CACHE_DIR`):

- `listing.json` — the last task listing shown (see above), via `ListingState.default()`. Not
  per account: it's keyed by list ID, which never matches across accounts.
- `<account key>/` — the cache, one directory per signed-in account (`cache_store.account_key`,
  a hash of the client ID and refresh token, so accounts never see each other's data; `current`
  names the active one). Inside: `tasklists.json` (all lists plus what `@default` resolved to)
  and `lists/<sha256(id)>.json` (one list's open tasks).

All of these follow `utils/json_files.py`: a semver `schema` per file (readers accept the same
MAJOR and treat anything else as missing — bump MAJOR for shape/meaning changes, MINOR for added
fields), atomic owner-only writes, and unreadable/corrupt files reading as missing and failed
writes being skipped, so they can never break a command. `gtasks auth` clears the whole folder.
New app-managed files should go here and use the same helpers. Always read the location as
`defaults.CACHE_DIR` at call time (never `from gtasks.defaults import CACHE_DIR`), so the single
override in `tests/conftest.py` keeps every test off the real `~/.cache`.

## Conventions

- Google API types (`Task`, `TaskList`, `TasksResource`) come from `google-api-python-client-stubs`
  and are imported under `if TYPE_CHECKING:` only — they do not exist at runtime.
- Heavy libraries (the Google API/auth packages, `httplib2`, `dateparser`; ~0.6 s together) are
  imported inside the functions that use them, never at module level, so a command served from
  the cache doesn't load them. `CachingClient` likewise builds the real client (`make_inner`)
  only on first use. `tests/test_startup.py` guards this in a subprocess. In tests, patch these
  names at their source module (e.g. `google_auth_oauthlib.flow.InstalledAppFlow`).
- `TasksClient` (`client/protocol.py`) is a `Protocol`, not an ABC — deliberately, so plain
  `Mock()`/`MagicMock()` test doubles satisfy it with no `spec=` or subclassing.
- ruff: line-length 100, rules `E,F,I,W`, `gtasks` as first-party for isort.
- Tests: `test_<fn>_GIVEN_<condition>_THEN_<result>` naming, grouped in `Test*` classes, with a
  `MagicMock` service fixture per module. `tests/conftest.py` holds only the autouse
  output/env/cache-dir isolation fixture; other fixtures stay per-module.
