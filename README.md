## gtasks-cli 

A simple Google Tasks CLI.

**Note**: Google technically supports having multiple task lists with the same title, but I wouldn't recommend it.

If developing, I'd recommend installing `uv` to help manage dependencies and virtual envs (`brew install uv` on MacOS). Then, you can run the following commands from the root of the cloned repo:
* `uv sync` will sync dependencies 
* `uv run gtasks/app.py` will run the script
* `uv run pytest` will run tests

Since you need to authenticate with your own API credentials, run `uv run gtasks/app.py setup` for explanation on how to generate and download your own `credentials.json` from the Google console in your browser. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md), a similar project, docs for more info. Then, run the setup command

**TODO**:
* Filter `gtasks tasks` command so that it only searches/shows incomplete tasks
* Refine the cli layer
* **High Prio:** Add better doc explaining how to download/configure a credentials.json file for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).

*Stretch Goals*:
* Add tab-autocomplete that leverages the tasklists cache
* Figure out a better way of managing package version
