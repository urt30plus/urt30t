import contextlib
import logging

from ..bot import BotPlugin
from ..models import BotError, Event, EventType, Game, GameType, Player, PlayerState

logger = logging.getLogger(__name__)


class CorePlugin(BotPlugin):
    async def on_load(self) -> None:
        self.bot.register_event_handler(EventType.init_game, self.on_init_game)
        self.bot.register_event_handler(
            EventType.client_connect, self.on_client_connect
        )
        self.bot.register_event_handler(
            EventType.client_disconnect, self.on_client_disconnect
        )
        self.bot.register_event_handler(
            EventType.client_user_info, self.on_client_user_info
        )
        self.bot.register_event_handler(EventType.client_spawn, self.on_client_spawn)
        self.bot.register_event_handler(EventType.say, self.on_say)

    async def on_unload(self) -> None:
        pass

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
        if event.client:
            self.bot.game.players[event.client].state = PlayerState.ALIVE

    async def on_say(self, event: Event) -> None:
        logger.info("on_say_team: %r", event)