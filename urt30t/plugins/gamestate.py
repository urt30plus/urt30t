import logging

from urt30t import (
    BotPlugin,
    Game,
    GameType,
    Player,
    Team,
    bot_subscribe,
    events,
)

logger = logging.getLogger(__name__)


class Plugin(BotPlugin):
    @bot_subscribe
    async def on_init_game(self, event: events.InitGame) -> None:
        self.bot.game = Game(
            map_name=event.game_data["mapname"],
            type=GameType(event.game_data["g_gametype"]),
            match_mode=event.game_data.get("g_matchmode", "0") != "0",
        )

    @bot_subscribe
    async def on_warmup(self, event: events.Warmup) -> None:
        self.bot.game.warmup = event is not None

    @bot_subscribe
    async def on_init_round(self, event: events.InitRound) -> None:
        self.bot.game.warmup = event is None

    @bot_subscribe
    async def on_client_connect(self, event: events.ClientConnect) -> None:
        if player := self.bot.player(event.slot):
            logger.warning("existing player found in slot: %r", player)

    @bot_subscribe
    async def on_client_user_info(self, event: events.ClientUserInfo) -> None:
        data = event.user_data
        guid = data["cl_guid"]
        auth = data.get("authl")
        name = data["name"]
        ip_addr, _, _ = data["ip"].partition(":")
        if (player := self.bot.player(event.slot)) and player.guid == guid:
            if player.auth != auth:
                logger.warning("auth mismatch: %s -> %s", player.auth, auth)
                player.auth = auth
            if player.name != name:
                logger.warning("name mismatch: %s -> %s", player.name, name)
                player.name = name
            if player.ip_address != ip_addr:
                logger.warning(
                    "ip address mismatch: %s -> %s", player.ip_address, ip_addr
                )
                player.ip_address = ip_addr
            logger.info("updated %r", player)
            return

        player = Player(
            slot=event.slot,
            name=name,
            guid=guid,
            auth=auth,
            ip_address=ip_addr,
        )
        await self.bot.connect_player(player)
        logger.debug("created %r", player)

    @bot_subscribe
    async def on_client_user_info_changed(
        self, event: events.ClientUserinfoChanged
    ) -> None:
        # TODO: do we care about fun stuff, arm ban colors and model selection?
        if player := self.bot.player(event.slot):
            name = event.user_data["n"].removesuffix("^7")
            if name != player.name:
                logger.warning("name change: %s -> %s", player.name, name)
                # TODO: fire name change event
                pass
            if (
                team := Team(event.user_data["t"])
            ) is not player.team and player.team is not Team.SPECTATOR:
                logger.warning("team change: %s -> %s", player.team, team)
                # TODO: fire team change event
                pass
            player.name = name
            player.team = team

    @bot_subscribe
    async def on_account_validated(self, event: events.AccountValidated) -> None:
        if (player := self.bot.player(event.slot)) and player.auth != event.auth:
            logger.warning("auth mismatch: %s != %s", player.auth, event.auth)

    @bot_subscribe
    async def on_client_begin(self, event: events.ClientBegin) -> None:
        await self.bot.sync_player(event.slot)

    @bot_subscribe
    async def on_client_spawn(self, event: events.ClientSpawn) -> None:
        logger.debug(event)

    @bot_subscribe
    async def on_client_disconnect(self, event: events.ClientDisconnect) -> None:
        await self.bot.disconnect_player(event.slot)

    @bot_subscribe
    async def on_shutdown_game(self, event: events.ShutdownGame) -> None:
        logger.debug(event)
