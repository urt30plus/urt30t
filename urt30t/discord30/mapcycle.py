import asyncio
import logging
import time
from pathlib import Path

import aiofiles
import discord

from ..models import GameType
from . import EmbedUpdater

logger = logging.getLogger(__name__)

MapCycle = dict[str, dict[str, str]]


async def update(updater: EmbedUpdater, mapcycle_file: Path) -> None:
    message, embed = await asyncio.gather(
        updater.fetch_embed_message(),
        _create_embed(mapcycle_file, updater.embed_title),
    )
    if message:
        if _should_update_embed(message, embed):
            logger.info("Updating existing message: %s", message.id)
            await message.edit(embed=embed)
        else:
            logger.info("Existing message embed is up to date")
    else:
        logger.info("Sending new message")
        await updater.new_message(embed=embed)


async def _create_embed(mapcycle_file: Path, embed_title: str) -> discord.Embed:
    logger.info("Creating map cycle embed from: %s", mapcycle_file)
    try:
        cycle = await _parse_mapcycle(mapcycle_file)
    except Exception:
        logger.exception("Failed to parse map cycle file: %s", mapcycle_file)
        cycle = {}
    return _create_mapcycle_embed(cycle, embed_title)


def _should_update_embed(message: discord.Message, embed: discord.Embed) -> bool:
    curr_embed = message.embeds[0]
    curr_txt = curr_embed.description if curr_embed.description else ""
    new_txt = embed.description if embed.description else ""
    return curr_txt.strip() != new_txt.strip()


async def _parse_mapcycle(mapcycle_file: Path) -> MapCycle:
    async with aiofiles.open(mapcycle_file, mode="r", encoding="utf-8") as f:
        lines = await f.readlines()
    return _parse_mapcycle_lines(lines)


def _parse_mapcycle_lines(lines: list[str]) -> MapCycle:
    result: MapCycle = {}
    map_name = ""
    map_config = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "{":
            map_config = result[map_name]
        elif line == "}":
            map_config = None
        elif map_config is None:
            map_name = line
            result[map_name] = {}
        else:
            k, v = line.split(" ", maxsplit=1)
            map_config[k.strip()] = v.strip().strip("\"'")
    return result


def _create_mapcycle_embed(cycle: MapCycle, embed_title: str) -> discord.Embed:
    if cycle:
        descr = (
            "```\n"
            + "\n".join([f"{k:25} {_map_mode(v)}" for k, v in cycle.items()])
            + "```"
        )
        color = discord.Colour.blue()
    else:
        descr = "*Unable to retrieve map cycle*"
        color = discord.Colour.red()
    embed = discord.Embed(
        title=embed_title,
        description=descr,
        colour=color,
    )
    embed.add_field(
        name=f"{len(cycle)} maps",
        value=f"updated <t:{int(time.time())}>",
        inline=False,
    )

    return embed


def _map_mode(map_opts: dict[str, str]) -> str:
    if map_opts.get("mod_gungame", "0") == "1":
        result = GameType.GUNGAME.name + " d3mod"
    elif map_opts.get("mod_ctf", "0") == "1":
        result = GameType.CTF.name + " d3mod"
    else:
        game_type = map_opts.get("g_gametype", GameType.CTF.value)
        result = GameType(game_type).name
    if map_opts.get("g_instagib") == "1":
        result += " Instagib"

    return "" if result == GameType.CTF.name else f"({result})"
