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
* **High Prio:** Add deletion/completion by list number + multi-task operations, look into batched API calls.
* "Show completed" mode — fetch needsAction tasks, then read recently-completed tasks from a local cache (populated by `gtasks done`) to append as strikethrough. Avoids a second API call. Configurable via `gtasks config`.
* Extend the task cache to include full task metadata (due dates, notes, status) so display commands don't need to hit the API.
* `gtasks config` — interactive command for managing defaults (active list, show-completed mode, etc.).

*Stretch Goals*:
* Tab-autocomplete leveraging the tasklists cache
* Pretty formatting
* Async cache refresh
