import contextlib
import logging

from urt30t import (
    BotCommandHandler,
    BotError,
    BotPlugin,
    Event,
    Game,
    GameType,
    Group,
    Player,
    PlayerState,
    bot_command,
)

logger = logging.getLogger(__name__)


class GameState(BotPlugin):
    async def on_init_game(self, event: Event) -> None:
        logger.info("on_init_game: %r", event)
        if not event.data:
            logger.error("missing event data")
            raise BotError
        parts = event.data["text"].lstrip("\\").split("\\")
        data = dict(zip(parts[0::2], parts[1::2], strict=True))
        self.bot.game = Game(
            type=GameType(data["g_gametype"]), map_name=data["mapname"]
        )
        logger.info("updated game: %r", self.bot.game)

    async def on_client_connect(self, event: Event) -> None:
        if event.client:
            with contextlib.suppress(KeyError):
                del self.bot.game.players[event.client]

    async def on_client_disconnect(self, event: Event) -> None:
        if event.client:
            with contextlib.suppress(KeyError):
                del self.bot.game.players[event.client]

    async def on_client_user_info(self, event: Event) -> None:
        if event.client:
            player = Player(id=event.client)
            self.bot.game.players[player.id] = player

    async def on_client_spawn(self, event: Event) -> None:
        if event.client and event.client in self.bot.game.players:
            self.bot.game.players[event.client].state = PlayerState.ALIVE


class Commands(BotPlugin):
    async def on_say(self, event: Event) -> None:
        if not event.data:
            return
        logger.info("on_say_team: %r", event)
        command, data = self._lookup_command(event.data["text"])
        if command:
            # TODO: check if client has permission to exec command
            await command.handler(data)
        else:
            logger.warning("no command found: %s", event)

    async def on_say_team(self, event: Event) -> None:
        if not event.data:
            return
        logger.info("on_say_team: %r", event)
        command, data = self._lookup_command(event.data["text"])
        if command:
            # TODO: check if client has permission to exec command
            await command.handler(data)
        else:
            logger.warning("no command found: %s", event)

    async def on_say_tell(self, event: Event) -> None:
        if not event.data:
            return
        logger.info("on_say_tell: %r", event)
        command, data = self._lookup_command(event.data["text"])
        if command:
            # TODO: check if client has permission to exec command
            await command.handler(data)
        else:
            logger.warning("no command found: %s", event)

    @bot_command(level=Group.guest, alias="wtf")
    async def cmd_help(self, data: str | None = None) -> None:
        logger.info("cmd_help called: %s", data)

    def _lookup_command(self, text: str) -> tuple[BotCommandHandler | None, str | None]:
        if text.startswith("!") and len(text) > 1:
            cmd, _, data = text[1:].partition(" ")
            handler = self.bot.find_command(cmd)
            return handler, data
        return None, None
