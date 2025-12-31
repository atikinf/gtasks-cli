## gtasks-cli 

A simple Google Tasks CLI.

If developing, I'd recommend installing `uv` to help manage dependencies and virtual envs (`brew install uv` on MacOS). 
Then, `uv sync` will sync dependencies and `uv run gtasks/cli.py` will run the script.

**Note:** you'll need to generate and download your own credentials.json from the Google console in your browser to access the Tasks API and oauth your account. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md) docs for more info.

**TODO**:
* Add unit testing for the tasks helper
* Add tab-autocomplete that leverages the tasklists cache
* Figure out a better way of managing package version

* **High Prio:** Add better doc explaining how to download/configure a credentials.json file for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).