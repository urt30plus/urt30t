import logging

from urt30t import (
    BotPlugin,
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
        logger.debug(event)
        game = self.bot.game
        data = event.game_data
        game.type = GameType(data["g_gametype"])
        game.time = event.game_time
        game.scores = None
        game.map_name = data["mapname"]
        game.match_mode = data.get("g_matchmode", "0") != "0"

    @bot_subscribe
    async def on_warmup(self, event: events.Warmup) -> None:
        logger.debug(event)
        self.bot.game.warmup = True

    @bot_subscribe
    async def on_init_round(self, event: events.InitRound) -> None:
        logger.debug(event)
        # TODO: assert or check that previous state was Warmup?
        self.bot.game.warmup = False

    @bot_subscribe
    async def on_client_connect(self, event: events.ClientConnect) -> None:
        logger.debug(event)
        if player := self.bot.player(event.slot):
            logger.warning("existing player found in slot: %r", player)

    @bot_subscribe
    async def on_client_user_info(self, event: events.ClientUserInfo) -> None:
        logger.debug(event)
        guid = event.user_data["cl_guid"]
        auth = event.user_data.get("authl")
        name = event.user_data["name"]
        ip_addr, _, _ = event.user_data["ip"].partition(":")
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
        logger.debug(event)
        # TODO: do we care about funstuff, armban colors and model selection?
        if player := self.bot.player(event.slot):
            name = event.user_data["n"].removesuffix("^7")
            if name != player.name:
                logger.warning("name change: %s -> %s", player.name, name)
                # TODO: fire name change event
                pass
            if (
                team := Team(event.user_data["t"])
            ) is not player.team and player.team is not Team.UNKNOWN:
                logger.warning("team change: %s -> %s", player.team, team)
                # TODO: fire team change event
                pass
            player.name = name
            player.team = team

    @bot_subscribe
    async def on_account_validated(self, event: events.AccountValidated) -> None:
        logger.debug(event)
        if (player := self.bot.player(event.slot)) and player.auth != event.auth:
            logger.warning("%s != %s", player.auth, event.auth)

    @bot_subscribe
    async def on_client_begin(self, event: events.ClientBegin) -> None:
        logger.debug(event)
        await self.bot.sync_player(event.slot)

    @bot_subscribe
    async def on_client_spawn(self, event: events.ClientSpawn) -> None:
        logger.debug(event)

    @bot_subscribe
    async def on_client_disconnect(self, event: events.ClientDisconnect) -> None:
        logger.debug(event)
        await self.bot.disconnect_player(event.slot)
