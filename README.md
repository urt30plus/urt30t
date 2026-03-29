# |30+| Urban Terror Game Bot

## Status

The Game bot is still under development as a replacement for B3. Game log
parsing and the event/command handling mechanisms are in place, but many
commands and other features are not implemented yet.

## Requirements

- Urban Terror 4.3.4
- Requires Python 3.13+

## Configuration

The bot uses a TOML file for configuration. Here is an example. Save
this to a file, modify for your environment, and then pass the full
path to the file when running the program.

```toml
[bot]
name = "30+Bot"

# prefix for all chat messages sent by the bot
message_prefix = "^0(^230+Bot^0)^7:"

# date format used by the bot
# see https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
time_format = "%I:%M%p %Z %m/%d/%y"

# IANA time zone database format
# see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
time_zone_name = "UTC"

# full path to the `games.log` file
games_log = "~/server/q3ut4/games.log"

# SQLAlchemy url, ex. sqlite+aiosqlite:///file_path
db_url = "sqlite+aiosqlite:///~/.config/urt30t.sqlite"

# if set to true, extra logging of issued DML statements will be output
db_debug = false

# maximum backlog of events to store, if more events come in
# they will be discarded
event_queue_max_size = 100

# prefix to use for issuing bot commands from chat
# for example, $balance
command_prefix = "!"

# list of plugins to enable on startup
plugins = []

# delay between reading lines from the games.log
log_read_delay = 0.250

# if you rotote the games.log, then enable this setting
log_check_truncated = false

# if enabled will read all events in the games.log, the default
# setting is to only read new lines
log_replay_from_start = false

[rcon]
host = "127.0.0.1"
port = 27960
password = ""
recv_timeout = 0.25

[log_levels]
root = "WARNING"
core = "INFO"
rcon = "INFO"
plugins = "INFO"
```

## Running

The project uses the [uv](https://docs.astral.sh/uv/) tool for
dependency management.

### Installation

The following will create a `.venv` directory and install only the
runtime dependencies:

    uv sync --upgrade --no-dev

### Run the module

    uv run -m urt30t

Or you can run it from the virtualenv:

Linux:

    .venv/bin/python -m urt30t

Windows:

    .venv\Scripts\python -m urt30t

To set up as a `systemd` service, see the sample `etc/systemd/urt30t.service`
file.

## Developing

### Installation

The following will create a `.venv` directory and install both the
runtime and development dependencies:

    uv sync --upgrade

### Install pre-commit

Recommend installing as a tool:

    uv tool install pre-commit

### Install the pre-commit hooks

    pre-commit install

### Run the checks

    bash run_checks.sh

### Reloading

To run the bot and have it reload when changes are made, use the following
command:

    watchfiles urt30t.__main__.main

## Service

```systemd
[Unit]
Description=UrT 4.3 Game Bot
After=urt43.service
StartLimitIntervalSec=120
StartLimitBurst=20

[Install]
WantedBy=multi-user.target

[Service]
Type=exec
CPUAffinity=1-2
Environment=UV_COMPILE_BYTECODE=1 UV_NO_DEV=1 UV_FROZEN=1 PYTHONUNBUFFERED=1
WorkingDirectory=%h/urt30t
ExecStartPre=-git pull
ExecStartPre=-%h/.local/bin/uv sync
ExecStart=%h/urt30t/.venv/bin/python -m urt30t %h/.config/urt30t.toml
Restart=on-failure
RestartSec=5
```
