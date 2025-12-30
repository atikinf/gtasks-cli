## gtasks-cli 

A simple Google Tasks CLI.

If developing, you can run `pip install -e .` in the base dir for an editable install of `gtasks`, callable from any dir.

Note, you'll need to generate and download your own credentials.json from the Google console in your browser to access the Tasks API and oauth your account. See [gcalcli's](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md) docs for more info.

**TODO**:
* Add unit testing for the tasks helper
* Add tab-autocomplete that leverages the tasklists cache
* Figure out a better way of managing package version

* **High Prio:** Add doc explaining how to download/configure a credentials.json file for new users. À la [gcalcli](https://github.com/insanum/gcalcli/blob/HEAD/docs/api-auth.md).