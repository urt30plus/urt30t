import logging
import re

from urt30t import (
    BotCommand,
    Group,
    Team,
    bot_command,
    settings,
)

logger = logging.getLogger(__name__)

CI_PING_THRESHOLD = 500
MAX_SLAPS = 10

team_map = {
    "red": Team.RED,
    "r": Team.RED,
    "blue": Team.BLUE,
    "b": Team.BLUE,
    "spectator": Team.SPECTATOR,
    "spec": Team.SPECTATOR,
    "s": Team.SPECTATOR,
}


@bot_command(Group.MODERATOR)
async def cmd_aliases(cmd: BotCommand, pid: str) -> None:
    """
    <player> - list all aliases used by the given player
    """
    await cmd.message(f"NotImplementedError: {pid}")
    raise NotImplementedError


@bot_command(Group.ADMIN, alias="bal")
async def cmd_balance(cmd: BotCommand) -> None:
    """
    Move as few players as needed to create teams balanced by numbers and skill.
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.ADMIN)
async def cmd_ban(cmd: BotCommand, pid: str, reason: str | None = None) -> None:
    """
    <player> [<reason>] - ban a player
    """
    await cmd.message(f"NotImplementedError: {pid} - {reason}")
    raise NotImplementedError


@bot_command(Group.MODERATOR)
async def cmd_baninfo(cmd: BotCommand, pid: str) -> None:
    """
    <player> - displays a player's ban information
    """
    await cmd.message(f"NotImplementedError: {pid}")
    raise NotImplementedError


@bot_command(Group.ADMIN)
async def cmd_bigtext(cmd: BotCommand, message: str) -> None:
    """
    <message> - prints a bold message in the center of all screens
    """
    await cmd.context.rcon.bigtext(message)


@bot_command(Group.ADMIN)
async def cmd_caplimit(cmd: BotCommand, limit: str | None = None) -> None:
    """
    [<limit>] - if limit is given, sets the cvar else returns the current setting
    """
    await _set_var_or_show_var(cmd, "caplimit", limit)


@bot_command(Group.MODERATOR)
async def cmd_ci(cmd: BotCommand, pid: str) -> None:
    """
    <player> - kick a client that has an interrupted connection
    """
    player = cmd.get_player(pid)
    gameinfo = await cmd.context.rcon.game_info()
    for p in gameinfo.players:
        if p.slot == player.slot:
            if p.team is Team.SPECTATOR:
                await cmd.message(f"{p.clean_name} is a spectator and not CI")
            elif p.ping >= CI_PING_THRESHOLD:
                await cmd.context.rcon.kick(p.slot, "connection interrupt")
                await cmd.message(f"{p.clean_name} was kick due to CI: {p.ping}")
            else:
                await cmd.message(f"{p.clean_name} ping [{p.ping}] is not CI")
            break
    else:
        await cmd.message(f"{player.name} [{player.slot}] is no longer connected")


@bot_command(Group.MODERATOR)
async def cmd_clear(cmd: BotCommand, pid: str | None = None) -> None:
    """
    [<player>] - clear all warnings
    """
    await cmd.message(f"NotImplementedError: {pid}")
    raise NotImplementedError


@bot_command(Group.ADMIN, alias="maprotate")
async def cmd_cyclemap(cmd: BotCommand) -> None:
    """
    cycle to the next map
    """
    await cmd.context.rcon.cycle_map()


@bot_command(Group.MODERATOR)
async def cmd_force(cmd: BotCommand, pid: str, team: str) -> None:
    """
    <player> <[r]ed/[b]lue/[s]pec> - Move a player to the specified team.
    """
    if players := cmd.find_player(pid):
        if len(players) == 1:
            player = players[0]
        else:
            choose = ", ".join(p.name for p in players)
            await cmd.message(f"Which client: {choose}")
            return
    else:
        await cmd.message(f"No players found: {pid}")
        return

    if not (target := team_map.get(team)):
        choices = ", ".join(team_map)
        await cmd.message(f"Invalid team name [target]: use {choices}")
        return

    if player.team is target:
        await cmd.message(f"Player already on team {target.name}")
        return

    await cmd.context.rcon.force(player.slot, target.name)


@bot_command(Group.ADMIN)
async def cmd_fraglimit(cmd: BotCommand, limit: str | None = None) -> None:
    """
    [<limit>] - if limit is given, sets the cvar else returns the current setting
    """
    await _set_var_or_show_var(cmd, "fraglimit", limit)


@bot_command(level=Group.GUEST)
async def cmd_help(cmd: BotCommand, name: str | None = None) -> None:
    """Provides a list of commands available."""
    if name:
        if cmd_config := cmd.context.find_command_config(name):
            # TODO: verify player has access to command via group
            if doc_string := cmd_config.handler.__doc__:
                clean_doc = " ".join(x.strip() for x in doc_string.splitlines())
                message = f'"{clean_doc}"'
            else:
                message = "no help found for this command"
        else:
            message = f"command [{name}] not found"
    else:
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        message = f"there are {len(cmd.context.commands)} commands total"

    await cmd.message(message)


@bot_command(Group.GUEST)
async def cmd_iamgod(cmd: BotCommand) -> None:
    """
    registers self as the super admin
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.MODERATOR)
async def cmd_kick(cmd: BotCommand, pid: str, reason: str | None = None) -> None:
    """
    <player> [<reason>] - kick a player
    """
    player = cmd.get_player(pid)
    await cmd.context.rcon.kick(player.slot, reason)
    msg = f"{player.name} was kicked"
    if reason:
        msg += f" for {reason}"
    await cmd.message(msg)


@bot_command(Group.MODERATOR)
async def cmd_lastbans(cmd: BotCommand) -> None:
    """
    lists the 5 last bans
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.GUEST, alias="lt")
async def cmd_leveltest(cmd: BotCommand, pid: str | None = None) -> None:
    """
    [<player>] - display a user's status
    """
    if pid:
        player = cmd.get_player(pid)
        await cmd.message(f"{player.name} is in group {player.group}")
    else:
        await cmd.message(f"{cmd.player.group.name}")


@bot_command(Group.MODERATOR)
async def cmd_list(cmd: BotCommand) -> None:
    """
    lists all connected players
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.GUEST, alias="l")
async def cmd_lookup(cmd: BotCommand, pid: str) -> None:
    """
    <player> - lookup a player in the database
    """
    await cmd.message(f"NotImplementedError: {pid}")
    raise NotImplementedError


@bot_command(level=Group.MODERATOR)
async def cmd_map(cmd: BotCommand, map_name: str) -> None:
    """
    <map name> - switches to the given map
    """
    # TODO: check map list and provides close choices
    await cmd.context.rcon.map(map_name)


@bot_command(level=Group.ADMIN)
async def cmd_maprestart(cmd: BotCommand) -> None:
    """
    restarts the current map
    """
    await cmd.context.rcon.map_restart()


@bot_command(level=Group.MODERATOR)
async def cmd_maps(cmd: BotCommand) -> None:
    """
    returns the list of all maps on the server
    """
    if not (map_list := cmd.context.server.map_list):
        map_list = await _map_list_reload(cmd)
    lines = [re.sub(r"^ut\d*?_", "", m) for m in map_list]
    if lines:
        await cmd.message(", ".join(lines))
    else:
        await cmd.message("no maps found")


@bot_command(level=Group.MODERATOR)
async def cmd_mapsreload(cmd: BotCommand) -> None:
    """
    reloads the maps cache
    """
    await _map_list_reload(cmd)
    await cmd_maps(cmd)


async def _map_list_reload(cmd: BotCommand) -> list[str]:
    cmd.context.server.map_list = await cmd.context.rcon.maps()
    return cmd.context.server.map_list


@bot_command(level=Group.ADMIN)
async def cmd_moon(cmd: BotCommand, toggle: str) -> None:
    """
    <on|off> - sets moon mode
    """
    if toggle.lower() in settings.TRUE_VALUES:
        await _set_var_or_show_var(cmd, "g_gravity", "100")
    else:
        await _set_var_or_show_var(cmd, "g_gravity", "800")


@bot_command(level=Group.MODERATOR)
async def cmd_mute(cmd: BotCommand, pid: str, duration: str | None = None) -> None:
    """
    <player> [<duration>] - mutes a player
    """
    player = cmd.get_player(pid)
    await cmd.context.rcon.mute(player.slot, duration)
    msg = f"{player.name} muted"
    if duration:
        msg += f" for {duration}"
    await cmd.message(msg)


@bot_command(level=Group.ADMIN)
async def cmd_nuke(cmd: BotCommand, pid: str) -> None:
    """
    <player> - nukes a player
    """
    player = cmd.get_player(pid)
    await cmd.context.rcon.nuke(player.slot)


@bot_command(level=Group.ADMIN)
async def cmd_permban(cmd: BotCommand, pid: str, reason: str | None = None) -> None:
    """
    <player> [<reason>] - ban a player permanently
    """
    # TODO: reason should be mandatory
    player = cmd.get_player(pid)
    if player.ip_address:
        await cmd.context.rcon.ban(player.ip_address)

    # TODO: save ban to storage
    msg = f"{player.name} was perm banned"
    if reason:
        msg += f" for {reason}"
    await cmd.message(msg)


@bot_command(Group.ADMIN)
async def cmd_putgroup(cmd: BotCommand, pid: str, group_name: str) -> None:
    """
    <player> <group> - adds a player to a group
    """
    await cmd.message(f"NotImplementedError: {pid} - {group_name}")
    raise NotImplementedError


@bot_command(level=Group.ADMIN)
async def cmd_reload(cmd: BotCommand) -> None:
    """
    reloads the current map
    """
    await cmd.context.rcon.reload()


@bot_command(level=Group.MODERATOR)
async def cmd_seen(cmd: BotCommand, pid: str) -> None:
    """
    <player> - displays the time the player was last seen
    """
    await cmd.message(f"NotImplementedError: {pid}")
    raise NotImplementedError


@bot_command(level=Group.ADMIN)
async def cmd_setnextmap(cmd: BotCommand, map_name: str) -> None:
    """
    <map name> - set the next map to be played
    """
    await cmd.message(f"NotImplementedError {map_name}")
    raise NotImplementedError


@bot_command(level=Group.ADMIN)
async def cmd_shuffleteams(cmd: BotCommand) -> None:
    """
    shuffle teams
    """
    await cmd.context.rcon.shuffle_teams()


@bot_command(Group.ADMIN, alias="sk")
async def cmd_skuffle(cmd: BotCommand) -> None:
    """
    shuffle all players to create balanced teams by numbers and skill
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(level=Group.ADMIN)
async def cmd_slap(cmd: BotCommand, pid: str, amount: str = "1") -> None:
    """
    <player> [<amount>] - slaps a player
    """
    try:
        times = int(amount)
    except ValueError:
        times = -1
    if not 1 <= times <= MAX_SLAPS:
        await cmd.message(f"amount must be a number between 1 and {MAX_SLAPS}")
        return
    player = cmd.get_player(pid)
    for _ in range(times):
        await cmd.context.rcon.slap(player.slot)


@bot_command(Group.MODERATOR)
async def cmd_swap(cmd: BotCommand, pid1: str, pid2: str | None = None) -> None:
    """
    <player1> [player2] - swap players to opposite teams, if player2 is not given,
    the admin using the command is swapped with player1
    """
    await cmd.message(f"NotImplementedError: {pid1} - {pid2}")
    raise NotImplementedError


@bot_command(level=Group.ADMIN)
async def cmd_swapteams(cmd: BotCommand) -> None:
    """
    swaps current teams
    """
    await cmd.context.rcon.swap_teams()


@bot_command(Group.USER)
async def cmd_teams(cmd: BotCommand) -> None:
    """
    force team balancing, the player with the least time in a team will be switched
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.ADMIN)
async def cmd_tempban(
    cmd: BotCommand, pid: str, duration: str, reason: str | None = None
) -> None:
    """
    <player> <duration> [<reason>] - temporarily ban a player
    """
    await cmd.message(f"NotImplementedError: {pid} - {duration} - {reason}")
    raise NotImplementedError


@bot_command(Group.GUEST)
async def cmd_test(cmd: BotCommand) -> None:
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
async def cmd_timelimit(cmd: BotCommand, limit: str | None = None) -> None:
    """
    [<limit>] - if limit is given, sets the cvar else returns the current setting
    """
    await _set_var_or_show_var(cmd, "timelimit", limit)


@bot_command(Group.ADMIN)
async def cmd_unban(cmd: BotCommand, pid: str) -> None:
    """
    <player> - un-ban a player
    """
    player = cmd.get_player(pid)
    # TODO: get IP address saved in the bans table
    if player.ip_address:
        await cmd.context.rcon.unban(player.ip_address)

    # TODO: remove ban from bans table
    await cmd.message(f"{player.name} was unbanned")


@bot_command(Group.ADMIN)
async def cmd_ungroup(cmd: BotCommand) -> None:
    """
    <player> <group> - removes a player from a group
    """
    await cmd.message("NotImplementedError")
    raise NotImplementedError


@bot_command(Group.MODERATOR)
async def cmd_veto(cmd: BotCommand) -> None:
    """
    vetoes the current running Vote
    """
    await cmd.context.rcon.veto()


async def _set_var_or_show_var(
    cmd: BotCommand, name: str, value: str | None = None
) -> None:
    if value is not None:
        await cmd.context.rcon.setcvar(name, value)
    elif cvar := await cmd.context.rcon.cvar(name):
        await cmd.message(f"{name} is set to {cvar.value}")
