# |30+| Urban Terror Game/Discord Bot

## Status

The Discord updaters that post mapcycle and player updates are fairly complete.
They are both in use today in our `#mapcycle` channel in our Discord.

The Game bot is still under development as a replacement for B3. Game log
parsing and the event/command handling mechanisms are in place, but many
commands and other features are not implemented yet.

## Requirements

- Urban Terror 4.3.4
- Requires Python 3.11+

## Configuration

The bot uses OS Environment Variables for its settings. See the
`urt30t.settings` module for all settings that are available.

## Running

### Create a virtual environment

    python3.11 -m venv .venv311

### Install the dependencies

    .venv311/bin/pip install -r requirements.txt

### Set the appropriate Environment Variables

You can either place these in a file named `.env` in the project root folder
or source them before running the module.

The following shows the settings required to run the Discord updaters:

```shell
export URT30T_FEATURE_DISCORD_UPDATES=on
export URT30T_FEATURE_LOG_PARSING=off
export URT30T_FEATURE_EVENT_DISPATCH=off
export URT30T_FEATURE_COMMAND_DISPATCH=off

export URT30T_RCON_HOST=127.0.0.1
export URT30T_RCON_PORT=27960
export URT30T_RCON_PASSWORD=supersekret
export URT30T_GAME_HOST=game.example.org

export URT30T_DISCORD_USER=YourBot#1337
export URT30T_DISCORD_TOKEN=<bot token>
export URT30T_DISCORD_SERVER_NAME=My Urban Terror Discord Server
export URT30T_DISCORD_UPDATES_CHANNEL_NAME=mapcycle

export URT30T_DISCORD_GAMEINFO_UPDATES_ENABLED=true
export URT30T_DISCORD_GAMEINFO_EMBED_TITLE=Current Map

export URT30T_DISCORD_MAPCYCLE_UPDATES_ENABLED=true
export URT30T_DISCORD_MAPCYCLE_EMBED_TITLE=Map Cycle
```

### Run the module

    .venv311/bin/python -m urt30t

To set up as a `systemd` service, see the sample `etc/systemd/urt30t.service` file.

## Developing

### Create a virtual environment

    python3.11 -m venv .venv311

### Install the development dependencies

    .venv311/bin/pip install -r requirements-dev.txt

### Install pre-commit. Recommend using `pipx`, but can also install locally using

    .venv311/bin/pip install pre-commit

### Install the pre-commit hooks

    pre-commit install

### Set the appropriate Environment Variables

Create a `.env` file in the project root with the appropriate settings

### Run the checks

    bash run_checks.sh

### Reloading

To run the bot and have it reload when changes are made, use the following
command:

    watchfiles urt30t.__main__.main
