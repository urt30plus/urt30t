import asyncio
import logging
import time

import discord

from .. import rcon, settings
from ..models import Game, Player
from .client import DiscordClient

logger = logging.getLogger(__name__)

START_TICK = time.monotonic()

# Max embed field length is roughly 48. We use 18 to display the
# ` [K../D./A.] 123ms` scores, and we want to leave a few chars
# for it to fit comfortably
EMBED_NO_PLAYERS = "```\n" + " " * (24 + 18) + "\n```"


def format_player(p: Player) -> str:
    ping = f"{p.ping:3}ms" if p.ping > 0 else ""
    return f"{p.name[:24]:24} [{p.kills:3}/{p.deaths:2}/{p.assists:2}] {ping}"


def player_score_display(players: list[Player]) -> str | None:
    if not players:
        return None

    return "```\n" + "\n".join([format_player(p) for p in players]) + "\n```"


def add_player_fields(embed: discord.Embed, server: Game) -> None:
    team_r = player_score_display(server.team_red)
    team_b = player_score_display(server.team_blue)
    if team_r or team_b:
        embed.add_field(
            name=f"Red ({server.score_red})",
            value=team_r or EMBED_NO_PLAYERS,
            inline=False,
        )
        embed.add_field(
            name=f"Blue ({server.score_blue})",
            value=team_b or EMBED_NO_PLAYERS,
            inline=False,
        )
    elif team_free := player_score_display(server.team_free):
        embed.add_field(name="Players", value=team_free, inline=False)

    if server.spectators:
        specs = "```\n" + "\n".join(p.name for p in server.spectators) + "\n```"
        embed.add_field(name="Spectators", value=specs, inline=False)


def add_mapinfo_field(embed: discord.Embed, game: Game) -> None:
    player_count = len(game.players)
    info = f"{game.time} / Total:{player_count:2}"
    if (spec_count := len(game.spectators)) != player_count:
        if (free_count := len(game.team_free)) > 0:
            if spec_count:
                info += f"  F:{free_count:2}"
        else:
            info += f"  R:{len(game.team_red):2}  B:{len(game.team_blue):2}"
        if spec_count:
            info += f"  S:{spec_count:2}"
    info = f"```\n{info}\n```"
    embed.add_field(name="Game Time / Player Counts", value=info, inline=False)


def create_server_embed(game: Game | None) -> discord.Embed:
    embed = discord.Embed(title=settings.discord.current_map_embed_title)

    last_updated = f"updated <t:{int(time.time())}:R>"
    connect_info = f"`/connect game.urt-30plus.org:{settings.rcon.port}`"

    if game:
        if game_type := game.type:
            description = f"{game.map_name} ({game_type})"
        else:
            description = game.map_name
        embed.description = f"```\n{description}\n```"
        if game.players:
            embed.colour = discord.Colour.green()
            add_mapinfo_field(embed, game)
            add_player_fields(embed, game)
            embed.add_field(name=connect_info, value=last_updated, inline=False)
        else:
            embed.colour = discord.Colour.light_grey()
            # do not add a field to make updating based on description only
            embed.description += "\n*No players online*\n"
            embed.description += f"\n{connect_info}\n{last_updated}"
    else:
        embed.colour = discord.Colour.red()
        embed.description = "*Unable to retrieve server information*"
        # add last updated as a field to trigger updating
        embed.add_field(name=connect_info, value=last_updated, inline=False)

    return embed


async def fetch_game(rcon_client: rcon.RconClient) -> Game | None:
    try:
        result = await rcon_client.players()
        return Game.from_dict(result)
    except Exception:
        logger.exception("Failed to get server info")
        return None


def should_update_embed(message: discord.Message, embed: discord.Embed) -> bool:
    current_embed = message.embeds[0]
    # embed fields indicate that either players are connected or there was an
    # error getting server info, in either case we want to continue updating
    if current_embed.fields or embed.fields:
        return True
    curr_txt = current_embed.description if current_embed.description else ""
    new_txt = embed.description if embed.description else ""
    # ignore the last line that has the updated timestamp embedded, at this
    # point the messages are `no players online` and we only want to update
    # if the map has changed
    return new_txt.rsplit("\n", maxsplit=1)[0] != curr_txt.rsplit("\n", maxsplit=1)[0]


def same_map_and_specs(s1: Game | None, s2: Game | None) -> bool:
    """
    Used to determine if both game instances reference the same map and
    have the same spectators with no current players. In case we can skip
    updating the embedded message.
    """
    return (
        s1 is not None
        and s2 is not None
        and s1.map_name == s2.map_name
        and len(s1.players) == len(s2.players)
        and len(s1.spectators) == len(s1.players)
        and len(s2.spectators) == len(s2.players)
        and sorted(s1.spectators) == sorted(s2.spectators)
    )


async def run(client: DiscordClient, rcon_client: rcon.RconClient) -> None:
    logger.info("Game Info Updater Start: %s", client)
    channel_name = settings.discord.update_channel_name
    embed_title = settings.discord.current_map_embed_title
    delay_players = settings.discord.current_map_update_delay
    delay_no_players = settings.discord.current_map_update_delay_no_players
    prev_game = None
    while True:
        channel_message, game = await asyncio.gather(
            client.fetch_embed_message(channel_name, embed_title),
            fetch_game(rcon_client),
        )
        channel, message = channel_message
        embed = create_server_embed(game)
        if message:
            if should_update_embed(message, embed):
                logger.info("Updating existing message: %s", message.id)
                await message.edit(embed=embed)
                delay = delay_players
            else:
                logger.info("Existing message embed is up to date")
                delay = delay_no_players
        else:
            logger.info("Sending new message")
            await channel.send(embed=embed)
            delay = delay_players

        if same_map_and_specs(prev_game, game):
            delay = delay_no_players

        prev_game = game

        await asyncio.sleep(delay)
