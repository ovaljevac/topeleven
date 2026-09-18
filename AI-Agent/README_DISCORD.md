# Discord Control for the Top Eleven Agent

The bot can start only pre-approved Top Eleven workflows. It does not accept arbitrary terminal commands.

## 1. Create a Discord application

1. Open the Discord Developer Portal and create a **New Application**.
2. In the **Bot** section, create a bot and copy its token. Never share the token or commit it to Git.
3. Under **OAuth2 > URL Generator**, select `bot` and `applications.commands`.
4. Grant these bot permissions: `View Channels`, `Send Messages`, and `Use Slash Commands`.
5. Open the generated URL and add the bot to your server.

Message Content Intent is not required because the bot uses slash commands.

## 2. Configure access

The easiest option is to double-click `Postavi Discord Bot.cmd`. It opens three dialogs for the token, Server ID, and User ID, then creates the configuration automatically.

Alternatively, copy `discord_config.example.json` to `discord_config.json` and enter:

- `token`: the bot token from the Developer Portal
- `guild_id`: the Discord server ID, which makes commands appear immediately
- `allowed_user_ids`: your Discord User ID; additional user IDs may be added
- `live_log`: set to `true` to receive automatic log messages

To copy an ID, enable **Discord Settings > Advanced > Developer Mode**, then right-click the server or user and select **Copy ID**.

## 3. Install and run

If `python --version` does not work, install a current Python 3 release from python.org and enable **Add Python to PATH** during installation.

From the `AI-Agent` directory in PowerShell:

```powershell
python -m pip install -r requirements.txt
```

Then double-click `Pokreni Discord Bot.cmd`. Its window must remain open while the bot is in use.

## Commands

- `/skripte` — lists the allowed workflows
- `/pokreni` — selects and starts a workflow
- `/sve`, `/zeleni`, `/odmor`, `/tv`, `/mourinho`, `/kampus`, `/savez`, `/trening` — immediately start the requested workflow without an additional selection or click
- `/restart` — fully stops the configured BlueStacks instance, starts Top Eleven again, and waits for home-screen confirmation
- `/start` — starts Top Eleven if it is closed; if it is already running, brings it to the foreground
- `/status` — shows the active workflow and elapsed time
- `/log` — shows the last 20 log lines
- `/stop` or `/zaustavi` — sends the agent's existing safe-stop signal

The bot intentionally permits only one active script because every workflow controls the same BlueStacks instance.
