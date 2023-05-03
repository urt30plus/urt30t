import difflib
import logging

from urt30t import (
    Bot,
    BotCommand,
    BotPlugin,
    CommandHandler,
    Group,
    MessageType,
    Team,
    bot_command,
    bot_subscribe,
    events,
)

from ..models import PlayerNotFoundError, TooManyPlayersFoundError

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
        """
        <player> - kick a client that has an interrupted connection
        """
        # TODO: have a command way to express required command args and show
        #   help if not present. Maybe catch AssertionError in on_say??
        assert len(cmd.args) >= 1
        player = self.get_player(cmd.args[0])
        gameinfo = await self.bot.rcon.players()
        for slot in gameinfo.get("Slots", []):
            if slot["slot"] == player.slot:
                try:
                    ping = int(slot["ping"])
                except ValueError:
                    ping = 999
                if ping >= 500:
                    # TODO: fix
                    await cmd.message("yep, ci")
                    return

        await cmd.message("not ci")

    @bot_command(Group.ADMIN)
    async def cyclemap(self, _: BotCommand) -> None:
        await self.bot.rcon.cycle_map()

    @bot_command(Group.MODERATOR)
    async def force(self, cmd: BotCommand) -> None:
        """
        <player> <[r]ed/[b]lue/[s]pec> - Move a player to the specified team.
        """
        if len(cmd.args) != 2:
            await cmd.message(f"Invalid arguments: {cmd.args}")
            return

        if players := self.bot.find_player(cmd.args[0]):
            if len(players) == 1:
                player = players[0]
            else:
                choose = ", ".join(p.name for p in players)
                await cmd.message(f"Which client: {choose}")
                return
        else:
            await cmd.message(f"No players found: {cmd.args[0]}")
            return

        if not (target := self.team_map.get(cmd.args[1])):
            choices = ", ".join(self.team_map)
            await cmd.message(f"Invalid team name [target]: use {choices}")
            return

        if player.team is target:
            await cmd.message(f"Player already on team {target.name}")
            return

        await self.bot.rcon.force(player.slot, target.name)

    @bot_command(Group.ADMIN)
    async def fraglimit(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(level=Group.GUEST)
    async def help(self, cmd: BotCommand) -> None:  # noqa: A003
        """Provides a list of commands available."""
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        if cmd.args:
            if cmd_handler := self._find_command_handler(cmd.args[0], cmd.player.group):
                message = f'"{cmd_handler.__doc__}"'
            else:
                message = f"command [{cmd.args[0]}] not found"
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
        logger.debug(cmd.args)
        await cmd.message(f"{cmd.player.group.name}")

    @bot_command(level=Group.ADMIN)
    async def map_restart(self, cmd: BotCommand) -> None:
        assert cmd.player
        await self.bot.rcon.map_restart()

    @bot_command(level=Group.MODERATOR)
    async def maps(self, cmd: BotCommand) -> None:
        # TODO: cache maps somewhere, maybe self.bot.server?
        #   check for cache and if not populated call maps_reload()
        map_list = await self.bot.rcon.maps()
        await cmd.message(f"found {len(map_list)} maps")

    @bot_command(level=Group.MODERATOR)
    async def maps_reload(self, cmd: BotCommand) -> None:
        # TODO: re-cache the maps list
        raise NotImplementedError

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

    @bot_command(Group.GUEST)
    async def test(self, cmd: BotCommand) -> None:
        msg = (
            "This is a really long line\n that should cause a wrap "
            "if things are working right.\n If not then some fixing "
            "will be required."
        )
        await cmd.message(msg)

    @bot_command(Group.ADMIN)
    async def timelimit(self, cmd: BotCommand) -> None:
        raise NotImplementedError

    @bot_command(Group.ADMIN)
    async def veto(self, cmd: BotCommand) -> None:
        raise NotImplementedError

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
        cmd = BotCommand(
            plugin=self,
            message_type=message_type,
            player=player,
            args=[x.strip() for x in data.split()],
        )
        if cmd_handler := self._find_command_handler(name, player.group):
            try:
                await cmd_handler(cmd)
            except PlayerNotFoundError as exc:
                await cmd.message(f"Player not found: {exc}", MessageType.PRIVATE)
            except TooManyPlayersFoundError as exc:
                choices = ", ".join(f"{p.name}" for p in exc.players)
                await cmd.message(f"Which player? {choices}", MessageType.PRIVATE)
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
