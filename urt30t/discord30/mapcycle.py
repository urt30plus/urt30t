import asyncio
import logging
import time

import aiofiles
import discord

from .. import rcon, settings
from ..models import GameType
from .client import DiscordClient

logger = logging.getLogger(__name__)

MapCycle = dict[str, dict[str, str]]


def map_mode(map_opts: dict[str, str]) -> str:
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


def parse_mapcycle_lines(lines: list[str]) -> MapCycle:
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


async def parse_mapcycle(mapcycle_file: str) -> MapCycle:
    async with aiofiles.open(mapcycle_file, mode="r", encoding="utf-8") as f:
        lines = await f.readlines()
    return parse_mapcycle_lines(lines)


def create_mapcycle_embed(cycle: MapCycle) -> discord.Embed:
    if cycle:
        descr = (
            "```\n"
            + "\n".join([f"{k:25} {map_mode(v)}" for k, v in cycle.items()])
            + "```"
        )
        color = discord.Colour.blue()
    else:
        descr = "*Unable to retrieve map cycle*"
        color = discord.Colour.red()
    embed = discord.Embed(
        title=settings.discord.mapcycle_embed_title,
        description=descr,
        colour=color,
    )
    embed.add_field(
        name=f"{len(cycle)} maps",
        value=f"updated <t:{int(time.time())}>",
        inline=False,
    )

    return embed


async def create_embed() -> discord.Embed:
    logger.info("Creating map cycle embed from: %s", settings.discord.mapcycle_file)
    try:
        cycle = await parse_mapcycle(settings.discord.mapcycle_file)
    except Exception:
        logger.exception(
            "Failed to parse map cycle file: %s", settings.discord.mapcycle_file
        )
        cycle = {}
    return create_mapcycle_embed(cycle)


def should_update_embed(message: discord.Message, embed: discord.Embed) -> bool:
    curr_embed = message.embeds[0]
    curr_txt = curr_embed.description if curr_embed.description else ""
    new_txt = embed.description if embed.description else ""
    return curr_txt.strip() != new_txt.strip()


async def update_mapcycle(client: DiscordClient) -> None:
    channel_message, embed = await asyncio.gather(
        client.fetch_embed_message(
            settings.discord.update_channel_name, settings.discord.mapcycle_embed_title
        ),
        create_embed(),
    )
    channel, message = channel_message
    if message:
        if should_update_embed(message, embed):
            logger.info("Updating existing message: %s", message.id)
            await message.edit(embed=embed)
        else:
            logger.info("Existing message embed is up to date")
    else:
        logger.info("Sending new message")
        await channel.send(embed=embed)


async def run(client: DiscordClient, rcon_client: rcon.RconClient) -> None:
    logger.info("Map Cycle Updater Started: %s", client)
    logger.debug(rcon_client)
    delay = settings.discord.mapcycle_update_delay
    timeout = settings.discord.mapcycle_update_timeout
    while True:
        try:
            await asyncio.wait_for(update_mapcycle(client), timeout=timeout)
        except Exception:
            logger.exception("Failed to update map cycle")
        await asyncio.sleep(delay)
