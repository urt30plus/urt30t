import difflib
import logging

from urt30t import (
    Bot,
    BotCommand,
    BotPlugin,
    CommandHandler,
    GameState,
    GameType,
    Group,
    MessageType,
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
        self.command_prefixes = tuple(x.value for x in MessageType)
        self.commands_by_group: dict[str, Group] = {}

    async def plugin_load(self) -> None:
        for cmd in self.bot.commands.values():
            self.commands_by_group[cmd.name] = cmd.level
            if cmd.alias:
                self.commands_by_group[cmd.alias] = cmd.level

    @bot_command(Group.ADMIN, alias="bal")
    async def balance(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def ban(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def bigtext(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def caplimit(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def ci(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def cyclemap(self, cmd: BotCommand) -> None:
        assert cmd.player
        assert not cmd.data
        await self.bot.rcon.cycle_map()

    @bot_command(Group.MODERATOR)
    async def force(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def fraglimit(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.GUEST)
    async def help(self, cmd: BotCommand) -> None:  # noqa: A003
        """Provides a list of commands available."""
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        if cmd.data:
            if cmd_handler := self._find_command_handler(cmd.data, cmd.player.group):
                message = f'"{cmd_handler.__doc__}"'
            else:
                message = f"command [{cmd.data}] not found"
        else:
            message = f"there are {len(self.bot.commands)} commands total"

        await cmd.message(message)

    @bot_command(Group.MODERATOR)
    async def kick(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def lastbans(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.GUEST, alias="lt")
    async def leveltest(self, cmd: BotCommand) -> None:
        # TODO: handle cases where data is another user to test
        logger.debug(cmd.data)
        await cmd.message(f"{cmd.player.group.name}")

    @bot_command(level=Group.ADMIN)
    async def map_restart(self, cmd: BotCommand) -> None:
        assert cmd.player
        await self.bot.rcon.map_restart()

    @bot_command(level=Group.ADMIN)
    async def moon(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.MODERATOR)
    async def mute(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def nuke(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def pause(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def putgroup(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def reload(self, cmd: BotCommand) -> None:
        assert cmd.player
        await self.bot.rcon.reload()

    @bot_command(level=Group.ADMIN)
    async def setnextmap(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def shuffleteams(self, cmd: BotCommand) -> None:
        assert cmd.player
        await self.bot.rcon.shuffle_teams()

    @bot_command(Group.ADMIN, alias="sk")
    async def skuffle(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def slap(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def swap(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def swapteams(self, cmd: BotCommand) -> None:
        assert cmd.player
        await self.bot.rcon.swap_teams()

    @bot_command(Group.USER)
    async def teams(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def tempban(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def timelimit(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def veto(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_subscribe
    async def on_say(self, event: events.Say) -> None:
        if not event.text.startswith(self.command_prefixes):
            return
        logger.info(event)
        if not (player := self.bot.find_player(event.slot)):
            logger.warning("no player found at: %s", event.slot)
            return
        message_type = MessageType(event.text[:1])
        name, _, data = event.text[1:].partition(" ")
        cmd = BotCommand(
            plugin=self, message_type=message_type, player=player, data=data
        )
        if cmd_handler := self._find_command_handler(name, player.group):
            await cmd_handler(cmd)
        else:
            logger.warning("no command config found: %s", event)
            if candidates := self._find_command_sounds_like(name, player.group):
                msg = f"did you mean? {', '.join(candidates)}"
            else:
                msg = f"command [{name}] not found"
            await cmd.message(msg, MessageType.PRIVATE)

    @bot_subscribe
    async def on_say_team(self, event: events.SayTeam) -> None:
        await self.on_say(event)

    @bot_subscribe
    async def on_say_tell(self, event: events.SayTell) -> None:
        if event.slot == event.target:
            await self.on_say(event)

    def _find_command_handler(
        self, cmd_name: str, group: Group
    ) -> CommandHandler | None:
        # TODO: verify group >= cmd.level
        assert group
        if cmd_config := self.bot.commands.get(cmd_name):
            return cmd_config.handler
        for c in self.bot.commands.values():
            if c.alias == cmd_name:
                return c.handler
        return None

    def _find_command_sounds_like(self, cmd_name: str, group: Group) -> set[str]:
        if len(cmd_name) < 2:
            return set()

        result = {
            name
            for name, level in self.commands_by_group.items()
            if cmd_name in name and level <= group
        }

        # catch misspellings
        if more := difflib.get_close_matches(cmd_name, self.commands_by_group):
            result.update(x for x in more if self.commands_by_group[str(x)] <= group)

        return result
