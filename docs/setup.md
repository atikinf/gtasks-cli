# Setting up Google sign-in

gtasks talks to Google Tasks with your own Google OAuth client: a small, free project in the
Google Cloud console that only you use. Setting it up takes about five minutes and is a
one-time job.

You'll end up with a **client ID** (`…apps.googleusercontent.com`) and a **client secret**,
which `gtasks auth` asks for, and a sign-in saved on your machine.

> Google Cloud is free for this: the Tasks API has no charge and no billing account is needed.

## 1. Create a project

1. Open the [Google Cloud console](https://console.cloud.google.com/) and sign in with the
   Google account whose tasks you want to use.
2. Open the project picker at the top of the page and click **New project**.
3. Give it any name (e.g. `gtasks`) and click **Create**. Make sure it's selected afterwards.

## 2. Enable the Google Tasks API

1. Go to [**APIs & Services → Library**](https://console.cloud.google.com/apis/library).
2. Search for **Google Tasks API**, open it, and click **Enable**.

Skipping this step makes every command fail with a `403` error mentioning
`accessNotConfigured` or "has not been used in project".

## 3. Configure the consent screen

In the console menu, open **Google Auth platform** (if it asks you to get started, do so).

1. **Branding**: set an app name (e.g. `gtasks`) and pick your email as the user support and
   developer contact email. Save.
2. **Audience**:
   - User type: **External** (pick **Internal** only if your account belongs to a Google
     Workspace organization and you'll only ever use gtasks with it).
   - Under **Test users**, click **Add users** and add your own Google account. While the app
     is in *Testing*, only test users can sign in; anyone else gets
     `Error 403: access_denied`.
3. **Data Access** can be left alone: gtasks asks for the Tasks scope
   (`https://www.googleapis.com/auth/tasks`) when you sign in.

### Avoid signing in again every week (recommended)

While the app's publishing status is **Testing**, Google expires the sign-in after **7 days**,
and gtasks will then say your sign-in expired and ask you to run `gtasks auth` again.

To stop that, go to **Audience** and, under **Publishing status**, click **Publish app**. You
don't need to submit anything for verification: it's your own app, used only by you. Google
will keep showing an "unverified app" notice when you sign in (step 5), which is expected.

## 4. Create the OAuth client

1. In **Google Auth platform → Clients**, click **Create client**.
2. Application type: **Desktop app**. Name: anything (e.g. `gtasks CLI`). Click **Create**.
3. **Copy the client ID and client secret now**, or click **Download JSON**. Since 2025 Google
   shows the secret only once, at creation; afterwards the console shows just its last few
   characters. If you lose it, add a new secret to the client (or create a new client).

## 5. Sign in with gtasks

```
gtasks auth
```

Paste the client ID and the client secret when asked (`q` cancels). Your browser opens a Google
sign-in page:

1. Choose the account you added as a test user.
2. You'll see **"Google hasn't verified this app"**. That's your own app, so click
   **Continue** (in some versions: **Advanced → Go to gtasks (unsafe)**).
3. Allow access to Google Tasks.

The browser then says the flow is complete and gtasks prints *Authenticated*. Try `gtasks lists`.

### Alternative: use the downloaded JSON instead of pasting

Save the file you downloaded in step 4 as `credentials.json` in gtasks' config directory:

```
mkdir -p ~/.config/gtasks-cli
mv ~/Downloads/client_secret_*.json ~/.config/gtasks-cli/credentials.json
```

Then just run any command (e.g. `gtasks`): with no saved sign-in, it opens the browser sign-in
using that file. This also means a sign-in that expires later is redone automatically.

## Where things are stored

In `$XDG_CONFIG_HOME/gtasks-cli` (default `~/.config/gtasks-cli`):

| File | What |
|---|---|
| `token.json` | Your saved sign-in (readable only by you). Refreshed automatically. |
| `credentials.json` | Only if you used the alternative above. |
| `config.ini` | Settings (`gtasks config`), including the active list. |

The client secret you paste into `gtasks auth` isn't stored separately; Google's sign-in token
includes what's needed to refresh itself.

## Troubleshooting

| You see | Fix |
|---|---|
| `Error 403: access_denied` in the browser | Add your account under **Audience → Test users** (step 3), or publish the app. |
| `Error 401: invalid_client` in the browser | The client ID or secret is wrong. Copy them again, or add a new secret to the client. |
| Lost the client secret | Google shows it only once. In **Google Auth platform → Clients**, open your client and add a new secret, then run `gtasks auth` and paste it. |
| `403` … `accessNotConfigured` / "API has not been used" | Enable the Google Tasks API for the same project (step 2). Changes can take a minute. |
| "Your Google sign-in has expired or was revoked" every week | The app is still in *Testing*: publish it (step 3), then run `gtasks auth`. |
| Invalid input when pasting the client ID | It should look like `123456789012-abc….apps.googleusercontent.com`. Paste the whole ID. |
| The browser doesn't open (e.g. over SSH) | Sign in on a machine with a browser, then copy `~/.config/gtasks-cli/token.json` to the same place on the other machine. |

### Running `gtasks auth` again

When you're already signed in, `gtasks auth` offers your current client as the default for each
prompt, shortened (the ends of the client ID, the secret's last four characters) and dimmed:

```
You're signed in. Press Enter to keep each value ('q' cancels).
Enter the client ID [1234...-...abcd.apps.googleusercontent.com]:
Enter the client secret [****Xy9z]:
Sign in again (e.g. as a different Google account)? [y/N]
```

- **Enter, Enter, Enter** keeps your sign-in (refreshing it if needed); nothing opens.
- Answer **y** to sign in again in the browser, e.g. as a **different Google account**.
- Paste a **new client ID** (and its secret) to switch to another OAuth client; that always
  signs in again.

Your current sign-in is only replaced once the new one succeeds, so cancelling (`q`, or closing
the browser tab and pressing Ctrl-C) leaves it working.

To revoke gtasks' access entirely, remove it under
[Google Account → Third-party connections](https://myaccount.google.com/connections).
