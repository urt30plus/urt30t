import asyncio
import logging
import time

import discord

from .. import rcon
from ..models import Game, Player
from . import DiscordAPIClient, DiscordEmbedUpdater

logger = logging.getLogger(__name__)

# Max embed field length is roughly 48. We use 18 to display the
# ` [K../D./A.] 123ms` scores, and we want to leave a few chars
# for it to fit comfortably
EMBED_NO_PLAYERS = "```\n" + " " * (24 + 18) + "\n```"


class GameInfoUpdater(DiscordEmbedUpdater):
    def __init__(
        self,
        api_client: DiscordAPIClient,
        rcon_client: rcon.RconClient,
        channel_name: str,
        embed_title: str,
    ) -> None:
        super().__init__(api_client, rcon_client, channel_name, embed_title)
        self._last_game: Game | None = None

    async def update(self) -> bool:
        message, game = await asyncio.gather(
            self.fetch_embed_message(),
            self.fetch_game_info(),
        )

        if message and same_map_and_specs(game, self._last_game):
            result = False
        else:
            embed = create_server_embed(game, self.embed_title)
            result = await self._update_or_create_if_needed(message, embed)

        self._last_game = game
        return result

    async def fetch_game_info(self) -> Game:
        game = await self.rcon_client.players()
        return Game.from_dict(game)

    def should_update_embed(
        self, message: discord.Message, embed: discord.Embed
    ) -> bool:
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
        return (
            new_txt.rsplit("\n", maxsplit=1)[0] != curr_txt.rsplit("\n", maxsplit=1)[0]
        )


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


def create_server_embed(game: Game | None, title: str) -> discord.Embed:
    embed = discord.Embed(title=title)

    last_updated = f"updated <t:{int(time.time())}:R>"
    connect_info = "`/connect game.urt-30plus.org`"  # TODO: port number

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
