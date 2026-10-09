## gtasks-cli

A simple Google Tasks CLI.

### Setup

gtasks uses your own (free) Google OAuth client. In the [Google Cloud console](https://console.cloud.google.com/), enable the Google Tasks API, add yourself as a test user, and create an OAuth client of type *Desktop app*; then run `gtasks auth` and paste in its client ID and secret.

**[docs/setup.md](docs/setup.md)** walks through every step, including how to avoid re-signing in every 7 days, and troubleshooting.

### Usage

```
gtasks                    # first 10 open tasks in the active list
gtasks tasks              # all open tasks
gtasks lists              # all task lists (● marks the active one)
gtasks use Work           # set the active list and show it (omit the name to pick)
gtasks add "Buy milk" -d "next fri" --notes "2%"
gtasks done 1 3           # by the numbers shown in the last listing, or by title
gtasks done milk          # part of a title works too, if only one task matches
gtasks delete "Buy milk"  # a partial title asks before deleting (-y to skip)
```

Tasks are listed in the same order as the Google Tasks app, with subtasks shown under their parent (`└`).

Titles ignore case. If part of a title matches several tasks or lists, you pick one from a numbered list; if nothing matches, close spellings are suggested.

Commands act on the active list. Override it per command with `-l LIST`, or per shell with `GTASKS_LIST=LIST`. If no list is active, your default Google Tasks list is used.

Lists and tasks are cached for up to 30 minutes (in `~/.cache/gtasks-cli`), so repeat listings are instant; each listing says whether it came from the cache or refreshed it. Changes made in gtasks show up immediately. To see changes made elsewhere sooner, add `--refresh`, or turn caching off with `gtasks config cache off`.

### Tab completion

Task and list titles can be completed with Tab. Add one line to your shell config:

```
eval "$(gtasks completion zsh)"     # ~/.zshrc
eval "$(gtasks completion bash)"    # ~/.bashrc
gtasks completion fish | source     # ~/.config/fish/config.fish
```

Completion matches the start of a title, ignoring case, and uses the local cache only (so it's instant and works offline); if the cache has expired, run any listing to refresh it. In zsh and fish, tasks show their due date alongside.

### Use from Claude (MCP)

`gtasks-mcp` is an [MCP](https://modelcontextprotocol.io) server that lets Claude Code or Claude Desktop read and manage your tasks ("do I have any old outstanding tasks?"). Sign in with `gtasks auth` first: the server never opens a browser itself.

Claude Code, running from a checkout:

```
claude mcp add gtasks -- uv run --directory /path/to/gtasks-cli gtasks-mcp
```

Or install it with the `mcp` extra (`uv tool install --reinstall '/path/to/gtasks-cli[mcp]'`, which also updates an existing `gtasks` install) and point any MCP host at `gtasks-mcp`. GUI apps don't see your shell's `PATH`, so give Claude Desktop the full path in `claude_desktop_config.json`:

```json
{ "mcpServers": { "gtasks": { "command": "/Users/<you>/.local/bin/gtasks-mcp" } } }
```

Tools: `list_tasklists`, `list_tasks` (one list or all; filters for overdue and not-recently-updated, oldest first, capped by `limit`), `get_task`, `add_tasks`, `update_task`, `complete_tasks`, `reopen_tasks`, `delete_tasks`, `move_task`, `create_tasklist`. It shares the CLI's sign-in, cache and active list (`gtasks use`).

### Development

Install [`uv`](https://docs.astral.sh/uv/) (`brew install uv` on macOS), then from the repo root:
* `uv sync` syncs dependencies
* `uv run gtasks` runs the CLI
* `uv run pytest` runs tests

**TODO**:
* Verify `gtasks auth` end-to-end functionality.
* Add undo functionality, store recent history on disk for undo purposes.
* Add task editing — no way to fix a title/notes/due date typo today without deleting and recreating the task.
* Add tasklist management (`gtasks add-list`, delete a list) — lists can currently only be created/removed from the Google Tasks web UI/app; this CLI only manages tasks within existing lists.
* Add `gtasks undone` to reopen a task marked complete by mistake (narrower than the general undo above).

*Stretch Goals*:
* "Show completed" mode — fetch needsAction tasks, then read recently-completed tasks from a local cache (populated by `gtasks done`) to append as strikethrough. Avoids a second API call. Configurable via `gtasks config`.
* Bulk "clear completed tasks" for a list (wraps the Tasks API's `tasks.clear`).
* Subtask support (the Tasks API's `parent` field on a task).
* Move/reorder tasks, including moving a task to a different list (`tasks.move`).
