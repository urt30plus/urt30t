import difflib
import logging

from urt30t import (
    Bot,
    BotCommand,
    BotPlugin,
    Group,
    MessageType,
    Team,
    bot_command,
    bot_subscribe,
    events,
)

from ..models import BotCommandConfig, PlayerNotFoundError, TooManyPlayersFoundError

logger = logging.getLogger(__name__)


class Plugin(BotPlugin):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self.command_prefix = bot.command_prefix
        self.commands_by_group: dict[str, Group] = {}
        self.team_map = {
            "red": Team.RED,
            "r": Team.RED,
            "blue": Team.BLUE,
            "b": Team.BLUE,
            "spectator": Team.SPECTATOR,
            "spec": Team.SPECTATOR,
            "s": Team.SPECTATOR,
        }

    async def plugin_load(self) -> None:
        for cmd in self.bot.commands.values():
            self.commands_by_group[cmd.name] = cmd.level
            if cmd.alias:
                self.commands_by_group[cmd.alias] = cmd.level

    @bot_command(Group.MODERATOR)
    async def aliases(self, cmd: BotCommand, pid: str) -> None:
        """
        <player> - list all aliases used by the given player
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN, alias="bal")
    async def balance(self, cmd: BotCommand) -> None:
        """
        Move as few players as needed to create teams balanced by numbers AND skill.
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def ban(self, cmd: BotCommand, pid: str, reason: str | None = None) -> None:
        """
        <player> [<reason>] - ban a player
        """
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def baninfo(self, cmd: BotCommand, pid: str) -> None:
        """
        <player> - displays a player's ban information
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def bigtext(self, _: BotCommand, message: str) -> None:
        """
        <message> - prints a bold message in the center of all screens
        """
        await self.bot.rcon.bigtext(message)

    @bot_command(Group.ADMIN)
    async def caplimit(self, cmd: BotCommand, limit: str | None = None) -> None:
        """
        [<limit>] - if limit is given, sets the cvar else returns the current setting
        """
        await self._set_var_or_show_var(cmd, "caplimit", limit)

    @bot_command(Group.MODERATOR)
    async def ci(self, cmd: BotCommand, pid: str) -> None:
        """
        <player> - kick a client that has an interrupted connection
        """
        player = self.get_player(pid)
        gameinfo = await self.bot.rcon.game_info()
        for slot, p in gameinfo.players.items():
            if slot == player.slot and p.ping >= 500:
                # TODO: fix
                await cmd.message("yep, ci")
                return

        await cmd.message("not ci")

    @bot_command(Group.MODERATOR)
    async def clear(self, cmd: BotCommand, pid: str | None = None) -> None:
        """
        [<player>] - clear all tk points and warnings
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN, alias="maprotate")
    async def cyclemap(self, _: BotCommand) -> None:
        """
        cycle to the next map
        """
        await self.bot.rcon.cycle_map()

    @bot_command(Group.MODERATOR)
    async def force(self, cmd: BotCommand, pid: str, team: str) -> None:
        """
        <player> <[r]ed/[b]lue/[s]pec> - Move a player to the specified team.
        """
        if players := self.bot.find_player(pid):
            if len(players) == 1:
                player = players[0]
            else:
                choose = ", ".join(p.name for p in players)
                await cmd.message(f"Which client: {choose}")
                return
        else:
            await cmd.message(f"No players found: {pid}")
            return

        if not (target := self.team_map.get(team)):
            choices = ", ".join(self.team_map)
            await cmd.message(f"Invalid team name [target]: use {choices}")
            return

        if player.team is target:
            await cmd.message(f"Player already on team {target.name}")
            return

        await self.bot.rcon.force(player.slot, target.name)

    @bot_command(Group.ADMIN)
    async def fraglimit(self, cmd: BotCommand, limit: str | None = None) -> None:
        """
        [<limit>] - if limit is given, sets the cvar else returns the current setting
        """
        await self._set_var_or_show_var(cmd, "fraglimit", limit)

    @bot_command(level=Group.GUEST)
    async def cmd_help(self, cmd: BotCommand, name: str | None = None) -> None:
        """Provides a list of commands available."""
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        if name:
            if cmd_config := self._find_command_config(name, cmd.player_group()):
                if doc_string := cmd_config.handler.__doc__:
                    clean_doc = " ".join(x.strip() for x in doc_string.splitlines())
                    message = f'"{clean_doc}"'
                else:
                    message = "no help found for this command"
            else:
                message = f"command [{name}] not found"
        else:
            message = f"there are {len(self.bot.commands)} commands total"

        await cmd.message(message)

    @bot_command(Group.GUEST)
    async def iamgod(self, cmd: BotCommand) -> None:
        """
        registers self as the super admin
        """
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def kick(self, cmd: BotCommand, pid: str, reason: str | None = None) -> None:
        """
        <player> [<reason>] - kick a player
        """
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def lastbans(self, cmd: BotCommand) -> None:
        """
        lists the 5 last bans
        """
        raise NotImplementedError

    @bot_command(Group.GUEST, alias="lt")
    async def leveltest(self, cmd: BotCommand, pid: str) -> None:
        """
        [<player>] - display a user's status
        """
        # TODO: handle cases where data is another user to test
        logger.debug(pid)
        await cmd.message(f"{cmd.player_group().name}")

    @bot_command(Group.MODERATOR)
    async def cmd_list(self, cmd: BotCommand) -> None:
        """
        lists all connected players
        """
        raise NotImplementedError

    @bot_command(Group.GUEST, alias="l")
    async def lookup(self, cmd: BotCommand, pid: str) -> None:
        """
        <player> - lookup a player in the database
        """
        raise NotImplementedError

    @bot_command(level=Group.MODERATOR)
    async def cmd_map(self, cmd: BotCommand, map_name: str) -> None:
        """
        <map name> - switches to the given map
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def map_restart(self, _: BotCommand) -> None:
        """
        restarts the current map
        """
        await self.bot.rcon.map_restart()

    @bot_command(level=Group.MODERATOR)
    async def maps(self, cmd: BotCommand) -> None:
        """
        returns the list of all maps on the server
        """
        # TODO: cache maps somewhere, maybe self.bot.server?
        #   check for cache and if not populated call maps_reload()
        map_list = await self.bot.rcon.maps()
        await cmd.message(f"found {len(map_list)} maps")

    @bot_command(level=Group.MODERATOR)
    async def maps_reload(self, cmd: BotCommand) -> None:
        """
        reloads the maps cache
        """
        # TODO: re-cache the maps list
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def moon(self, cmd: BotCommand, toggle: str) -> None:
        """
        <on|off> - sets moon mode
        """
        raise NotImplementedError

    @bot_command(level=Group.MODERATOR)
    async def mute(
        self, cmd: BotCommand, pid: str, duration: str | None = None
    ) -> None:
        """
        <player> [<duration>] - mutes a player
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def nuke(self, _: BotCommand, pid: str) -> None:
        """
        <player> - nukes a player
        """
        player = self.get_player(pid)
        await self.bot.rcon.nuke(player.slot)

    @bot_command(level=Group.ADMIN)
    async def permban(self, cmd: BotCommand, name: str) -> None:
        """
        <player> [<reason>] - ban a player permanently
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def putgroup(self, cmd: BotCommand, pid: str, group_name: str) -> None:
        """
        <player> <group> - adds a player to a group
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def reload(self, cmd: BotCommand) -> None:
        """
        reloads the current map
        """
        assert cmd.player
        await self.bot.rcon.reload()

    @bot_command(level=Group.MODERATOR)
    async def seen(self, cmd: BotCommand, pid: str) -> None:
        """
        <player> - displays the time the player was last seen
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def setnextmap(self, cmd: BotCommand, map_name: str) -> None:
        """
        <map name> - set the next map to be played
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def shuffleteams(self, _: BotCommand) -> None:
        """
        shuffle teams
        """
        await self.bot.rcon.shuffle_teams()

    @bot_command(Group.ADMIN, alias="sk")
    async def skuffle(self, cmd: BotCommand) -> None:
        """
        shuffle all players to create balanced teams by numbers and skill
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def slap(self, cmd: BotCommand, pid: str, amount: str = "1") -> None:
        """
        <player> [<amount>] - slaps a player
        """
        try:
            times = int(amount)
        except ValueError:
            times = -1
        if not 1 <= times <= 10:
            await cmd.message("amount must be a number between 1 and 10")
            return
        player = self.get_player(pid)
        for _ in range(times):
            await self.bot.rcon.slap(player.slot)

    @bot_command(Group.MODERATOR)
    async def swap(self, cmd: BotCommand, pid1: str, pid2: str | None = None) -> None:
        """
        <player1> [player2] - swap players to opposite teams, if player2 is not given,
        the admin using the command is swapped with player1
        """
        raise NotImplementedError

    @bot_command(level=Group.ADMIN)
    async def swapteams(self, cmd: BotCommand) -> None:
        """
        swaps current teams
        """
        assert cmd.player
        await self.bot.rcon.swap_teams()

    @bot_command(Group.USER)
    async def teams(self, cmd: BotCommand) -> None:
        """
        force team balancing, the player with the least time in a team will be switched
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def tempban(
        self, cmd: BotCommand, pid: str, duration: str, reason: str | None = None
    ) -> None:
        """
        <player> <duration> [<reason>] - temporarily ban a player
        """
        raise NotImplementedError

    @bot_command(Group.GUEST)
    async def test(self, cmd: BotCommand) -> None:
        """
        just a test command, can do literally anything it may want
        """
        msg = (
            "This is a really long line\n that should cause a wrap "
            "if things are working right.\n If not then some fixing "
            "will be required."
        )
        await cmd.message(msg)

    @bot_command(Group.ADMIN)
    async def timelimit(self, cmd: BotCommand, limit: str | None = None) -> None:
        """
        [<limit>] - if limit is given, sets the cvar else returns the current setting
        """
        await self._set_var_or_show_var(cmd, "timelimit", limit)

    @bot_command(Group.ADMIN)
    async def unban(self, cmd: BotCommand) -> None:
        """
        <player> - un-ban a player
        """
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def ungroup(self, cmd: BotCommand) -> None:
        """
        <player> <group> - removes a player from a group
        """
        raise NotImplementedError

    @bot_command(Group.MODERATOR)
    async def veto(self, _: BotCommand) -> None:
        """
        vetoes the current running Vote
        """
        await self.bot.rcon.veto()

    async def _set_var_or_show_var(
        self, cmd: BotCommand, name: str, value: str | None = None
    ) -> None:
        if value is not None:
            await self.bot.rcon.setcvar(name, value)
        elif cvar := await self.bot.rcon.cvar(name):
            await cmd.message(f"{name} is set to {cvar.value}")

    @bot_subscribe
    async def on_say(self, event: events.Say) -> None:
        if not event.text.startswith(self.command_prefix):
            return
        logger.info(event)
        if not (player := self.bot.player(event.slot)):
            logger.warning("no player found at: %s", event.slot)
            return
        cmd_and_data = event.text.lstrip(self.command_prefix)
        prefix_count = len(event.text) - len(cmd_and_data)
        if not 1 <= prefix_count <= 3:
            logger.warning("too many command prefixes, ignoring: %s", event.text)
            return
        message_type = MessageType(len(event.text) - len(cmd_and_data))
        name, _, data = cmd_and_data.partition(" ")
        cmd_args = [x.strip() for x in data.split()]
        cmd = BotCommand(
            plugin=self,
            name=name,
            message_type=message_type,
            player=player,
            args=cmd_args,
        )
        if cmd_config := self._find_command_config(name, cmd.player_group()):
            if cmd_config.max_args == 0:
                cmd_args = []
            elif not cmd_config.min_args <= len(cmd_args) <= cmd_config.max_args:
                msg = (
                    f"invalid arguments, expected between {cmd_config.min_args} "
                    f"and {cmd_config.max_args} but got {len(cmd_args)}"
                )
                logger.error(msg)
                msg += f" see !help {name}"
                await cmd.message(msg, MessageType.PRIVATE)
                return
            try:
                await cmd_config.handler(cmd, *cmd_args)
            except PlayerNotFoundError as exc:
                await cmd.message(f"Player not found: {exc}", MessageType.PRIVATE)
            except TooManyPlayersFoundError as exc:
                choices = ", ".join(f"{p.name}" for p in exc.players)
                await cmd.message(f"Which player? {choices}", MessageType.PRIVATE)
        else:
            logger.warning("no command config found: %s", event)
            if candidates := self._find_command_sounds_like(name, cmd.player_group()):
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

    def _find_command_config(
        self, cmd_name: str, group: Group
    ) -> BotCommandConfig | None:
        # TODO: verify group >= cmd.level
        assert group
        if cmd_config := self.bot.commands.get(cmd_name):
            return cmd_config
        for c in self.bot.commands.values():
            if c.alias == cmd_name:
                return c
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
