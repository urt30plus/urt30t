import contextlib
import logging

from urt30t import (
    BotCommandHandler,
    BotPlugin,
    Event,
    GameState,
    GameType,
    Group,
    Player,
    PlayerState,
    Team,
    bot_command,
)

logger = logging.getLogger(__name__)


class GameStatePlugin(BotPlugin):
    async def on_init_game(self, event: Event) -> None:
        logger.debug("on_init_game: %r", event)
        if not event.data:
            logger.warning("missing event data")
            return
        data = self._parse_info_string(event.data["text"])
        self.bot.game.type = GameType(data["g_gametype"])
        self.bot.game.map_name = data["mapname"]
        # TODO: what about cap/frag/time limit and other settings

    async def on_warmup(self, event: Event) -> None:
        logger.debug("on_warmup: %r", event)
        self.bot.game.state = GameState.WARMUP

    async def on_init_round(self, event: Event) -> None:
        logger.debug("on_init_round: %r", event)
        self.bot.game.state = GameState.LIVE

    async def on_client_connect(self, event: Event) -> None:
        logger.debug("on_client_connect: %r", event)
        if event.client:
            with contextlib.suppress(KeyError):
                del self.bot.game.players[event.client]

    async def on_client_user_info(self, event: Event) -> None:
        logger.debug("on_client_user_info: %r", event)
        if event.client and event.data:
            data = self._parse_info_string(event.data["text"])
            ip_addr, _, _ = data["ip"].partition(":")
            player = Player(
                id=event.client,
                name=data["name"],
                guid=data["cl_guid"],
                auth=data.get("authl"),
                ip_address=ip_addr,
            )
            self.bot.game.players[player.id] = player

    async def on_client_user_info_changed(self, event: Event) -> None:
        logger.debug("on_client_user_info_changed: %r", event)
        if (
            event.client
            and event.data
            and (player := self.bot.game.players.get(event.client))
        ):
            data = self._parse_info_string(event.data["text"])
            player.name = data["n"]
            player.team = Team(data["t"])

    async def on_client_spawn(self, event: Event) -> None:
        logger.debug("on_client_spawn: %r", event)
        if event.client and event.client in self.bot.game.players:
            self.bot.game.players[event.client].state = PlayerState.ALIVE

    async def on_account_validated(self, event: Event) -> None:
        logger.debug("on_account_validated: %r", event)
        if (
            event.client
            and event.data
            and (player := self.bot.game.players.get(event.client))
        ):
            player.validated = True
            if player.auth != event.data["auth"]:
                logger.warning("%s != %s", player.auth, event.data["auth"])

    async def on_client_disconnect(self, event: Event) -> None:
        logger.debug("on_client_disconnect: %r", event)
        if event.client:
            with contextlib.suppress(KeyError):
                del self.bot.game.players[event.client]

    @staticmethod
    def _parse_info_string(data: str) -> dict[str, str]:
        parts = data.lstrip("\\").split("\\")
        return dict(zip(parts[0::2], parts[1::2], strict=True))


class CommandsPlugin(BotPlugin):
    async def on_say(self, event: Event) -> None:
        if not (event.data and event.client):
            return
        text = event.data.get("text")
        if not (text and text.startswith("!")):
            return
        logger.info("on_say_team: %r", event)
        command, data = self._lookup_command(text)
        if command:
            # TODO: check if client has permission to exec command
            player = self.bot.game.players[event.client]
            await command.handler(player, data)
        else:
            logger.warning("no command found: %s", event)

    async def on_say_team(self, event: Event) -> None:
        await self.on_say(event)

    async def on_say_tell(self, event: Event) -> None:
        await self.on_say(event)

    @bot_command(level=Group.guest, alias="wtf")
    async def cmd_help(self, player: Player, data: str | None = None) -> None:
        """Provides a list of commands available."""
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        if data:
            if cmd := self.bot.find_command(data):
                message = f'"{cmd.handler.__doc__}"'
            else:
                message = f"command [{data}] not found"
        else:
            message = "you asked for a list of all commands?"

        await self.bot.private_message(player, message)

    def _lookup_command(self, text: str) -> tuple[BotCommandHandler | None, str | None]:
        if text.startswith("!") and len(text) > 1:
            cmd, _, data = text[1:].partition(" ")
            handler = self.bot.find_command(cmd)
            return handler, data
        return None, None
