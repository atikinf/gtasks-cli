## gtasks-cli 

A simple Google Tasks CLI.

**Note**: Google technically supports having multiple task lists with the same title, but I wouldn't recommend it.

If developing, I'd recommend installing `uv` to help manage dependencies and virtual envs (`brew install uv` on MacOS). Then, you can run the following commands from the root of the cloned repo:
* `uv sync` will sync dependencies 
* `uv run gtasks/app.py` will run the script
* `uv run pytest` will run tests

Since you need to authenticate with your own API credentials, run `uv run gtasks/app.py auth` for explanation on how to generate and download your own `credentials.json` from the Google console in your browser. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md), a similar project, docs for more info. Then, run the auth command

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
* Pretty formatting
* Benchmark startup latency — profile lazy-importing `dateparser`, `googleapiclient.discovery`, and `google_auth_oauthlib.flow`.
* Bulk "clear completed tasks" for a list (wraps the Tasks API's `tasks.clear`).
* Subtask support (the Tasks API's `parent` field on a task).
* Move/reorder tasks, including moving a task to a different list (`tasks.move`).
