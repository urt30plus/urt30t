#!/usr/bin/env bash
set -xe

echo "CI is set to [${CI}]"
if [[ $CI != "true" ]]; then
    pre-commit run --all-files
fi

mypy --version
mypy

export URT30T_FEATURE_DISCORD_UPDATES=off
export URT30T_GAMES_LOG=README.md
export URT30T_RCON_PASSWORD=sekret

pytest
