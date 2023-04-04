#!/usr/bin/env bash
set -xe

echo "CI is set to [${CI}]"
if [[ $CI != "true" ]]; then
    pre-commit run --all-files
fi

mypy --version
mypy

export URT30T_GAMES_LOG=games.log
export URT30T_DB_URL=sqlite+aiosqlite:///./b3.sqlite

pytest
