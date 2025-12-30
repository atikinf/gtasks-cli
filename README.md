## gtasks-cli 

Putting together a simple Google Tasks CLI to make it easier to stay in the terminal and to re-familiarize myself with type hinted Python. 

**TODO**:
* Add an [ID -> Title, ETag] cache, stored as a pickle/json in the .config/gtasks-cli dir. Read each time a command is run. Can check against ETag to invlidate cache elements.
* Add tab-autocomplete that leverages the above cache.

* Add doc explaining how to download/configure a credentials.json file for new users.

**Disclaimer**: I'm making use of AI to speed things up here and there and to help with syntax for unfamiliar libraries. See AGENTS.md for some context.
