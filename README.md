# |30+| Urban Terror Game/Discord Bot

## Status

The Discord updaters that post mapcycle and player updates are fairly complete.
They are both in use today in our `#mapcycle` channel in our Discord.

The Game bot is still under development. Game log parsing and the event/command
handling mechanisms are in place, but many commands are not implemented. Also
missing is the database storage for players.

## Requirements

- Urban Terror 4.3.4
- Requires Python 3.11+

## Configuration

The bot uses OS Environment Variables for its settings. See the
`urt30t.settings` module for all settings that are available.

## Running

Create a virtual environment

    python3.11 -m venv .venv311

Install the dependencies

    .venv311/bin/pip install -r requirements.txt

Run the module

    .venv311/bin/python -m urt30t

To set up as a `systemd` service, see the sample `etc/systemd/urt30t.service` file.

## Developing

Create a `.env` file in the project root with the appropriate settings

Create a virtual environment

    python3.11 -m venv .venv311

Install the development dependencies

    .venv311/bin/pip install -r requirements-dev.txt

Install pre-commit. Recommend using `pipx`, but can also install locally using

    .venv311/bin/pip install pre-commit

Install the pre-commit hooks

    pre-commit install

Run the checks

    bash run_checks.sh

### Reloading

To run the bot and have it reload when changes are made, use the following
command:

    watchfiles urt30t.__main__.main
