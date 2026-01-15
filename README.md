## gtasks-cli 

A simple Google Tasks CLI.

**Note**: Google technically supports having multiple task lists with the same title, but I wouldn't recommend it.

If developing, I'd recommend installing `uv` to help manage dependencies and virtual envs (`brew install uv` on MacOS). Then, you can run the following commands from the root of the cloned repo:
* `uv sync` will sync dependencies 
* `uv run gtasks/cli.py` will run the script
* `uv run pytest` will run tests


**Note:** You'll need to generate and download your own `credentials.json` from the Google console in your browser to access the Tasks API and oauth your account. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md) docs for more info.

**TODO**:
* Filter `gtasks tasks` command so that it only searches/shows incomplete tasks
* Flesh out api_client with complete_task and update_task functionality
* Refine the cli layer
* **High Prio:** Add better doc explaining how to download/configure a credentials.json file for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).

*Stretch Goals*:
* Add tab-autocomplete that leverages the tasklists cache
* Figure out a better way of managing package version
