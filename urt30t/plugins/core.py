import difflib
import logging

from urt30t import (
    Bot,
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
        self.bot.game.state = GameState.WARMUP

    @bot_subscribe
    async def on_init_round(self, event: events.InitRound) -> None:
        logger.debug(event)
        # TODO: assert or check that previous state was Warmup?
        self.bot.game.state = GameState.LIVE

    @bot_subscribe
    async def on_client_connect(self, event: events.ClientConnect) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            logger.warning("existing player found in slot: %r", player)

    @bot_subscribe
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

    @bot_subscribe
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

    @bot_subscribe
    async def on_account_validated(self, event: events.AccountValidated) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            player.validated = True
            if player.auth != event.auth:
                logger.warning("%s != %s", player.auth, event.auth)

    @bot_subscribe
    async def on_client_begin(self, event: events.ClientBegin) -> None:
        logger.debug(event)
        await self.bot.sync_player(event.slot)

    @bot_subscribe
    async def on_client_spawn(self, event: events.ClientSpawn) -> None:
        logger.debug(event)
        if player := self.bot.find_player(event.slot):
            player.state = PlayerState.ALIVE

    @bot_subscribe
    async def on_client_disconnect(self, event: events.ClientDisconnect) -> None:
        logger.debug(event)
        await self.bot.disconnect_player(event.slot)


class CommandsPlugin(BotPlugin):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self.commands_by_group: dict[str, Group] = {}

    async def plugin_load(self) -> None:
        for cmd in self.bot.commands.values():
            self.commands_by_group[cmd.command.name] = cmd.command.level
            if cmd.command.alias:
                self.commands_by_group[cmd.command.alias] = cmd.command.level

    @bot_command(Group.ADMIN, alias="bal")
    async def balance(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def bigtext(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def caplimit(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def ci(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def cyclemap(self, player: Player, data: str | None = None) -> None:
        assert player
        assert not data
        await self.bot.rcon.cycle_map()

    @bot_command(Group.MODERATOR)
    async def force(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def fraglimit(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.GUEST)
    async def help(self, player: Player, data: str | None = None) -> None:  # noqa: A003
        """Provides a list of commands available."""
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        if data:
            if cmd := self._find_command(data):
                message = f'"{cmd.handler.__doc__}"'
            else:
                message = f"command [{data}] not found"
        else:
            message = f"there are {len(self.bot.commands)} commands total"

        await self.bot.rcon.private_message(player.slot, message)

    @bot_command(Group.GUEST, alias="lt")
    async def leveltest(self, player: Player, data: str | None = None) -> None:
        # TODO: handle cases where data is another user to test
        logger.debug(data)
        await self.bot.rcon.private_message(player.slot, f"{player.group.name}")

    @bot_command(level=Group.ADMIN)
    async def map_restart(self, player: Player, _: str | None = None) -> None:
        assert player
        await self.bot.rcon.map_restart()

    @bot_command(level=Group.ADMIN)
    async def moon(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.MODERATOR)
    async def mute(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def nuke(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def pause(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def reload(self, player: Player, _: str | None = None) -> None:
        assert player
        await self.bot.rcon.reload()

    @bot_command(level=Group.ADMIN)
    async def setnextmap(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def shuffleteams(self, player: Player, _: str | None = None) -> None:
        assert player
        await self.bot.rcon.shuffle_teams()

    @bot_command(Group.ADMIN, alias="sk")
    async def skuffle(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def slap(self, player: Player, _: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def swap(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def swapteams(self, player: Player, _: str | None = None) -> None:
        assert player
        await self.bot.rcon.swap_teams()

    @bot_command(Group.USER)
    async def teams(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def timelimit(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def veto(self, player: Player, data: str | None = None) -> None:
        raise NotImplementedError

    @bot_subscribe
    async def on_say(self, event: events.Say) -> None:
        if not event.text.startswith("!"):
            return
        logger.info(event)
        cmd, _, data = event.text[1:].partition(" ")
        command = self._find_command(cmd)
        if not (player := self.bot.find_player(event.slot)):
            logger.warning("no player found at: %s", event.slot)
            return
        if command:
            await command.handler(player, data)
        else:
            logger.warning("no command found: %s", event)
            if candidates := self._find_command_sounds_like(player.group, cmd):
                msg = f"did you mean? {', '.join(candidates)}"
            else:
                msg = f"command [{cmd}] not found"
            await self.bot.rcon.private_message(player.slot, msg)

    @bot_subscribe
    async def on_say_team(self, event: events.SayTeam) -> None:
        await self.on_say(event)

    @bot_subscribe
    async def on_say_tell(self, event: events.SayTell) -> None:
        if event.slot == event.target:
            await self.on_say(event)

    def _find_command(self, cmd: str) -> BotCommandHandler | None:
        if handler := self.bot.commands.get(cmd):
            return handler
        for ch in self.bot.commands.values():
            if ch.command.alias == cmd:
                return ch
        return None

    def _find_command_sounds_like(self, group: Group, cmd: str) -> set[str]:
        if len(cmd) < 2:
            return set()

        result = {
            name
            for name, level in self.commands_by_group.items()
            if cmd in name and level <= group
        }

        # catch misspellings
        if more := difflib.get_close_matches(cmd, self.commands_by_group):
            result.update(x for x in more if self.commands_by_group[x] <= group)

        return result
