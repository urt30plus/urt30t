#!/usr/bin/env bash
set -xe

export UV_FROZEN=1

uv run --active prek run --all-files
uv run --active ty check

export URT30T_CONFIG_FILE="./tests/test-config.toml"

uv run --active pytest -p no:cacheprovider
