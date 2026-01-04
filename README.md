## gtasks-cli 

A simple Google Tasks CLI.

**Note**: Google technically supports having multiple task lists with the same title. This package is built under the assumption that users will avoid doing that since it's silly and makes using the lists' human readable name impossible. If two lists are detected sharing a name a warning is printed to the terminal.

If developing, I'd recommend installing `uv` to help manage dependencies and virtual envs (`brew install uv` on MacOS). Then, you can run the following commands from the root of the cloned rpo:
* `uv sync` will sync dependencies 
* `uv run gtasks/cli.py` will run the script
* `uv run pytest` will run tests


**Note:** You'll need to generate and download your own `credentials.json` from the Google console in your browser to access the Tasks API and oauth your account. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md) docs for more info.

**TODO**:
* ToDo: Refactor the prompting aspect out of ConfigManager, instead TasksHelper should contain a Prompter and a ConfigManager and keep them separate logically, passing just the result of the prompt into the ConfigManager
* **High Prio:** Add better doc explaining how to download/configure a credentials.json file for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).
* Add unit testing for the tasks helper

*Stretch Goals*:
* Add tab-autocomplete that leverages the tasklists cache
* Figure out a better way of managing package version