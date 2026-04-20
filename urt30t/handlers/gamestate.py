import asyncio
import difflib
import logging

from urt30t import (
    BotCommand,
    BotError,
    FlagAction,
    Game,
    GameType,
    Group,
    Player,
    Team,
    bot_subscribe,
    events,
    settings,
)
from urt30t.models import (
    BotContext,
    MessageType,
    PlayerNotFoundError,
    TooManyPlayersFoundError,
)

logger = logging.getLogger(__name__)


@bot_subscribe
async def on_startup(ctx: BotContext, event: events.BotStarted) -> None:
    logger.info("%r", event)
    old_game = ctx.game
    for _ in range(5):
        try:
            rcon_game = await ctx.rcon.game_info()
            break
        except LookupError:
            await asyncio.sleep(1.5)
    else:
        return
    new_players = {
        p.slot: Player(
            slot=p.slot,
            name=p.clean_name,
            name_exact=p.name,
            auth=p.auth,
            guid=p.guid,
            team=p.team,
            # don't carry over kda, we'll track ourselves
            ip_address=p.ip_address,
        )
        for p in rcon_game.players
    }
    ctx.game = new_game = Game(
        map_name=rcon_game.map_name,
        type=rcon_game.type,
        warmup=rcon_game.warmup,
        match_mode=rcon_game.match_mode,
        score_red=rcon_game.score_red,
        score_blue=rcon_game.score_blue,
        players=new_players,
    )
    await asyncio.gather(*[_sync_player(ctx, slot) for slot in new_game.players])
    logger.debug("Game state:\nbefore: %r\nafter: %r", old_game, ctx.game)


@bot_subscribe
async def on_init_game(ctx: BotContext, event: events.InitGame) -> None:
    # TODO: save N number of previous Game states?
    ctx.game = Game(
        map_name=event.game_data["mapname"],
        type=GameType(event.game_data["g_gametype"]),
        warmup=True,
        match_mode=event.game_data.get("g_matchmode", "0") != "0",
    )


@bot_subscribe
async def on_warmup(ctx: BotContext, _: events.Warmup) -> None:
    ctx.game.warmup = True


@bot_subscribe
async def on_init_round(ctx: BotContext, _: events.InitRound) -> None:
    ctx.game.warmup = False


@bot_subscribe
async def on_client_connect(ctx: BotContext, event: events.ClientConnect) -> None:
    if player := ctx.game.players.get(event.slot):
        logger.warning("existing player found in slot: %r", player)


@bot_subscribe
async def on_client_user_info(ctx: BotContext, event: events.ClientUserInfo) -> None:
    data = event.user_data
    guid = data["cl_guid"]
    auth = data.get("authl", "")
    name = data["name"]
    ip_addr, _, _ = data["ip"].partition(":")
    if (player := ctx.game.players.get(event.slot)) and player.guid == guid:
        if player.auth != auth:
            logger.warning("auth mismatch: %s -> %s", player.auth, auth)
            player.auth = auth
        if player.name_exact != name:
            logger.warning("name mismatch: %s -> %s", player.name_exact, name)
            player.update_name(name)
        if player.ip_address != ip_addr:
            logger.warning("ip address mismatch: %s -> %s", player.ip_address, ip_addr)
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
    ctx.game.players[event.slot] = player
    logger.debug("created %r", player)


@bot_subscribe
async def on_client_user_info_changed(
    ctx: BotContext, event: events.ClientUserinfoChanged
) -> None:
    # TODO: do we care about fun stuff, arm ban colors and model selection?
    if player := ctx.game.players.get(event.slot):
        name = event.user_data["n"].removesuffix("^7")
        if name != player.name_exact:
            logger.warning("name change: %s -> %s", player.name_exact, name)
            # TODO: fire name change event
        if (
            team := Team(event.user_data["t"])
        ) is not player.team and player.team is not Team.SPECTATOR:
            logger.warning("team change: %s -> %s", player.team, team)
            # TODO: fire team change event
        player.update_name(name)
        player.update_team(team)


@bot_subscribe
async def on_account_validated(ctx: BotContext, event: events.AccountValidated) -> None:
    if (player := ctx.game.players.get(event.slot)) and player.auth != event.auth:
        logger.warning("auth mismatch: %s != %s", player.auth, event.auth)


@bot_subscribe
async def on_client_begin(ctx: BotContext, event: events.ClientBegin) -> None:
    await _sync_player(ctx, event.slot)


@bot_subscribe
async def on_client_spawn(ctx: BotContext, event: events.ClientSpawn) -> None:
    if not (player := ctx.game.players.get(event.slot)):
        player = await _sync_player(ctx, event.slot)
    player.alive_timer.start()


@bot_subscribe
async def on_client_disconnect(ctx: BotContext, event: events.ClientDisconnect) -> None:
    ctx.game.players.pop(event.slot, None)


@bot_subscribe
async def on_shutdown_game(ctx: BotContext, _: events.ShutdownGame) -> None:
    players = [(p.calc_xp(), p) for p in ctx.game.players.values()]
    players.sort(reverse=True)
    logger.debug("Players by XP:\n\t%s", "\n\t".join(f"{xp}: {p}" for xp, p in players))


@bot_subscribe
async def on_kill(ctx: BotContext, event: events.Kill) -> None:
    if ctx.game.warmup:
        return
    if victim := ctx.game.players.get(event.victim):
        victim.deaths += 1
        victim.alive_timer.stop()
        if player := ctx.game.players.get(event.slot):
            if player.team is not victim.team:
                player.kills += 1
                if ctx.game.type is GameType.TDM:
                    if player.team is Team.RED:
                        ctx.game.score_red += 1
                    else:
                        ctx.game.score_blue += 1
            else:
                # TODO: handle suicide?
                # TODO: handle tk?
                pass


@bot_subscribe
async def on_assist(ctx: BotContext, event: events.Assist) -> None:
    if ctx.game.warmup:
        return
    if player := ctx.game.players.get(event.slot):
        player.assists += 1


@bot_subscribe
async def on_flag_captured(ctx: BotContext, event: events.Flag) -> None:
    if event.action is FlagAction.CAPTURED:
        if event.team is Team.RED:
            ctx.game.score_red += 1
        else:
            ctx.game.score_blue += 1


@bot_subscribe
async def on_survivor_winner(ctx: BotContext, event: events.SurvivorWinner) -> None:
    if event.team is Team.RED:
        ctx.game.score_red += 1
    else:
        ctx.game.score_blue += 1


@bot_subscribe
async def on_say(ctx: BotContext, event: events.Say) -> None:
    if not event.text.startswith(settings.bot.command_prefix):
        return
    logger.info(event)
    if not (player := ctx.game.players.get(event.slot)):
        logger.warning("no player found at: %s", event.slot)
        return
    cmd_and_data = event.text.lstrip(settings.bot.command_prefix)
    prefix_count = len(event.text) - len(cmd_and_data)
    if prefix_count not in MessageType:
        logger.warning("too many command prefixes, ignoring: %s", event.text)
        return
    message_type = MessageType(prefix_count)
    name, _, data = cmd_and_data.partition(" ")
    cmd_args = [x.strip() for x in data.split()]
    cmd = BotCommand(
        context=ctx,
        name=name,
        message_type=message_type,
        player=player,
        args=cmd_args,
    )
    if cmd_config := ctx.find_command_config(name):
        # TODO: check player has access to this command via group
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
        if candidates := _find_command_sounds_like(ctx, name, cmd.player.group):
            msg = f"did you mean? {', '.join(candidates)}"
        else:
            msg = f"command [{name}] not found"
        await cmd.message(msg, MessageType.PRIVATE)


@bot_subscribe
async def on_say_team(ctx: BotContext, event: events.SayTeam) -> None:
    await on_say(ctx, event)


@bot_subscribe
async def on_say_tell(ctx: BotContext, event: events.SayTell) -> None:
    if event.slot == event.target:
        await on_say(ctx, event)


def _find_command_sounds_like(ctx: BotContext, cmd_name: str, group: Group) -> set[str]:
    if len(cmd_name) <= 1:
        return set()

    commands_by_group = {k: v.level for k, v in ctx.commands.items()}
    result = {
        name
        for name, level in commands_by_group.items()
        if cmd_name in name and level <= group
    }

    # catch misspellings
    if more := difflib.get_close_matches(cmd_name, commands_by_group):
        result.update(x for x in more if commands_by_group[str(x)] <= group)

    return result


async def _sync_player(ctx: BotContext, slot: str) -> Player:
    if not (player := ctx.game.players.get(slot)):
        raise BotError("invalid_slot", slot)

    if not (player.guid and player.auth):
        if userinfo := await ctx.rcon.dumpuser(slot):
            player.guid = userinfo["cl_guid"]
            player.auth = userinfo["authl"]
        else:
            logger.error("dumpuser failed for slot [%s]", slot)

    if not player.db_id:
        # TODO: await db.sync_player(player)
        # TODO: check for bans
        pass

    logger.info("%r", player)
    return player
