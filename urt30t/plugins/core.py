import logging

from urt30t import (
    BotCommandHandler,
    BotPlugin,
    GameState,
    GameType,
    Group,
    Player,
    PlayerState,
    Team,
    bot_command,
    bot_subscribe,
    events,
)

logger = logging.getLogger(__name__)


class GameStatePlugin(BotPlugin):
    @bot_subscribe(events.InitGame)
    async def on_init_game(self, event: events.InitGame) -> None:
        logger.debug(event)
        self.bot.game.type = GameType(event.game_data["g_gametype"])
        self.bot.game.map_name = event.game_data["mapname"]
        # TODO: what about cap/frag/time limit and match mode?

    @bot_subscribe(events.Warmup)
    async def on_warmup(self, event: events.Warmup) -> None:
        logger.debug(event)
        self.bot.game.state = GameState.WARMUP

    @bot_subscribe(events.InitRound)
    async def on_init_round(self, event: events.InitRound) -> None:
        logger.debug(event)
        # TODO: assert or check that previous state was Warmup?
        self.bot.game.state = GameState.LIVE

    @bot_subscribe(events.ClientConnect)
    async def on_client_connect(self, event: events.ClientConnect) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            logger.warning("existing player found in slot: %r", player)

    @bot_subscribe(events.ClientUserInfo)
    async def on_client_user_info(self, event: events.ClientUserInfo) -> None:
        logger.debug(event)
        guid = event.user_data["cl_guid"]
        auth = event.user_data.get("authl")
        name = event.user_data["name"]
        ip_addr, _, _ = event.user_data["ip"].partition(":")
        if (player := self.bot.find_player(event.slot)) and player.guid == guid:
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

    @bot_subscribe(events.ClientUserinfoChanged)
    async def on_client_user_info_changed(
        self, event: events.ClientUserinfoChanged
    ) -> None:
        logger.debug(event)
        # TODO: do we care about funstuff, armban colors and model selection?
        if player := self.bot.find_player(event.slot):
            if (name := event.user_data["n"]) != player.name:
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

    @bot_subscribe(events.AccountValidated)
    async def on_account_validated(self, event: events.AccountValidated) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            player.validated = True
            if player.auth != event.auth:
                logger.warning("%s != %s", player.auth, event.auth)

    @bot_subscribe(events.ClientBegin)
    async def on_client_begin(self, event: events.ClientBegin) -> None:
        logger.debug(event)
        # TODO: good time to load/save info to db?
        # TODO: check for bans

    @bot_subscribe(events.ClientSpawn)
    async def on_client_spawn(self, event: events.ClientSpawn) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            player.state = PlayerState.ALIVE

    @bot_subscribe(events.ClientDisconnect)
    async def on_client_disconnect(self, event: events.ClientDisconnect) -> None:
        logger.debug(event)
        await self.bot.disconnect_player(event.slot)

    @staticmethod
    def _parse_info_string(data: str) -> dict[str, str]:
        parts = data.lstrip("\\").split("\\")
        return dict(zip(parts[0::2], parts[1::2], strict=True))


class CommandsPlugin(BotPlugin):
    @bot_subscribe(events.Say)
    async def on_say(self, event: events.Say) -> None:
        if not event.text.startswith("!"):
            return
        logger.info(event)
        command, data = self._lookup_command(event.text)
        if command:
            if player := self.bot.find_player(event.slot):
                # TODO: check if client has permission to exec command
                await command.handler(player, data)
            else:
                logger.warning("slot %s no longer connected: %s", event.slot, command)
        else:
            logger.warning("no command found: %s", event)

    @bot_subscribe(events.SayTeam)
    async def on_say_team(self, event: events.SayTeam) -> None:
        await self.on_say(event)

    @bot_subscribe(events.SayTell)
    async def on_say_tell(self, event: events.SayTell) -> None:
        await self.on_say(event)

    @bot_command(level=Group.GUEST)
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
