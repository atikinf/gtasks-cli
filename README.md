## gtasks-cli

A simple Google Tasks CLI.

### Setup

You need your own Google OAuth client: in the [Google Cloud console](https://console.cloud.google.com/apis/credentials), enable the Tasks API and create an OAuth client ID (type: Desktop app). Then run `gtasks auth` and paste in the client ID and secret. See [gcalcli's auth docs](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md) for a walkthrough of a similar setup.

### Usage

```
gtasks                    # first 10 open tasks in the active list
gtasks tasks              # all open tasks
gtasks lists              # all task lists (● marks the active one)
gtasks use Work           # set the active list (omit the name to pick interactively)
gtasks add "Buy milk" -d "next fri" -n "2%"
gtasks done 1 3           # by the numbers shown in the last listing, or by title
gtasks delete "Buy milk"
```

Commands act on the active list. Override it per command with `-l LIST`, or per shell with `GTASKS_LIST=LIST`. If no list is active, your default Google Tasks list is used.

### Development

Install [`uv`](https://docs.astral.sh/uv/) (`brew install uv` on macOS), then from the repo root:
* `uv sync` syncs dependencies
* `uv run gtasks` runs the CLI
* `uv run pytest` runs tests

**TODO**:
* **High Prio:** Add better doc explaining how to download/configure a `credentials.json` for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).
* Verify `gtasks auth` end-to-end functionality.
* Add undo functionality, store recent history on disk for undo purposes.
* Add task editing — no way to fix a title/notes/due date typo today without deleting and recreating the task.
* Add tasklist management (`gtasks add-list`, delete a list) — lists can currently only be created/removed from the Google Tasks web UI/app; this CLI only manages tasks within existing lists.
* Add `gtasks undone` to reopen a task marked complete by mistake (narrower than the general undo above).

*Stretch Goals*:
* "Show completed" mode — fetch needsAction tasks, then read recently-completed tasks from a local cache (populated by `gtasks done`) to append as strikethrough. Avoids a second API call. Configurable via `gtasks config`.
* Tab-autocomplete for task list names
* Benchmark startup latency — profile lazy-importing `dateparser`, `googleapiclient.discovery`, and `google_auth_oauthlib.flow`.
* Bulk "clear completed tasks" for a list (wraps the Tasks API's `tasks.clear`).
* Subtask support (the Tasks API's `parent` field on a task).
* Move/reorder tasks, including moving a task to a different list (`tasks.move`).
