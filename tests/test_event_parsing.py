from urt30t import Team, events
from urt30t.events import LogEvent
from urt30t.models import BombAction, FlagAction, HitLocation, HitMode, KillMode


def test_event_account_kick() -> None:
    log_event = LogEvent(
        type=events.AccountKick, data="13 - [ABC]foobar^7 rejected: no account"
    )
    e = events.AccountKick.from_log_event(log_event)
    assert e.slot == "13"
    assert e.text == "[ABC]foobar^7 rejected: no account"


def test_event_account_rejected() -> None:
    log_event = LogEvent(type=events.AccountRejected, data='19 -  - "no account"')
    e = events.AccountRejected.from_log_event(log_event)
    assert e.slot == "19"
    assert e.text == '-  - "no account"'


def test_event_account_validated() -> None:
    log_event = LogEvent(type=events.AccountValidated, data='0 - m0neysh0t - 6 - ""')
    e = events.AccountValidated.from_log_event(log_event)
    assert e.slot == "0"
    assert e.auth == "m0neysh0t"


def test_event_assist() -> None:
    log_event = LogEvent(
        events.Assist,
        data="12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7",
    )
    e = events.Assist.from_log_event(log_event)
    assert e.slot == "12"
    assert e.killer == "1"
    assert e.victim == "0"


def test_event_bomb_defused() -> None:
    log_event = LogEvent(events.Bomb, data="defused by 11!")
    e = events.Bomb.from_log_event(log_event)
    assert e.slot == "11"
    assert e.action is BombAction.DEFUSED


def test_event_bomb_tossed() -> None:
    log_event = LogEvent(events.Bomb, data="tossed by 8")
    e = events.Bomb.from_log_event(log_event)
    assert e.slot == "8"
    assert e.action is BombAction.TOSSED


def test_event_bomb_holder() -> None:
    log_event = LogEvent(events.BombHolder, data="2")
    e = events.BombHolder.from_log_event(log_event)
    assert e.slot == "2"


def test_event_client_begin() -> None:
    log_event = LogEvent(events.ClientBegin, data="4")
    e = events.ClientBegin.from_log_event(log_event)
    assert e.slot == "4"


def test_event_client_connect() -> None:
    log_event = LogEvent(events.ClientConnect, data="15")
    e = events.ClientBegin.from_log_event(log_event)
    assert e.slot == "15"


def test_event_client_disconnect() -> None:
    log_event = LogEvent(events.ClientDisconnect, data="15")
    e = events.ClientDisconnect.from_log_event(log_event)
    assert e.slot == "15"


def test_event_client_melted() -> None:
    log_event = LogEvent(events.ClientMelted, data="15")
    e = events.ClientMelted.from_log_event(log_event)
    assert e.slot == "15"


def test_event_client_spawn() -> None:
    log_event = LogEvent(events.ClientSpawn, data="15")
    e = events.ClientSpawn.from_log_event(log_event)
    assert e.slot == "15"


def test_event_flag() -> None:
    log_event = LogEvent(events.Flag, data="0 2: team_CTF_redflag")
    e = events.Flag.from_log_event(log_event)
    assert e.slot == "0"
    assert e.action == FlagAction.CAPTURED
    assert e.team == Team.RED


def test_event_flag_capture_time() -> None:
    log_event = LogEvent(events.FlagCaptureTime, data="0: 15750")
    e = events.FlagCaptureTime.from_log_event(log_event)
    assert e.slot == "0"
    assert e.cap_time == 15.75


def test_event_freeze() -> None:
    log_event = LogEvent(
        events.Freeze, data="4 17 38: |30+|money^7 froze <>(CK)<>^7 by UT_MOD_M4"
    )
    e = events.Freeze.from_log_event(log_event)
    assert e.slot == "4"
    assert e.target == "17"
    assert e.freeze_mode == KillMode.M4


def test_event_hit() -> None:
    log_event = LogEvent(
        events.Hit, data="4 8 4 19: |30+|Mudcat^7 hit |30+|money^7 in the Vest"
    )
    e = events.Hit.from_log_event(log_event)
    assert e.slot == "4"
    assert e.attacker == "8"
    assert e.location is HitLocation.VEST
    assert e.hit_mode is HitMode.M4


def test_event_init_auth() -> None:
    log_event = LogEvent(
        events.InitAuth,
        data=r"\auth\0\auth_status\init\auth_cheaters\1\auth_tags\1\auth_notoriety\1\auth_groups\\auth_owners\579\auth_verbosity\1",
    )
    e = events.InitAuth.from_log_event(log_event)
    assert e.auth_data["auth_owners"] == "579"


def test_event_kill() -> None:
    log_event = LogEvent(
        events.Kill,
        data="8 5 46: |30+|Mudcat^7 killed |30+|BenderBot^7 by UT_MOD_TOD50",
    )
    e = events.Kill.from_log_event(log_event)
    assert e.slot == "8"
    assert e.victim == "5"
    assert e.kill_mode is KillMode.TOD50


def test_event_survivor_winner_player() -> None:
    log_event = LogEvent(events.SurvivorWinner, data="2")
    e = events.SurvivorWinner.from_log_event(log_event)
    assert e.slot == "2"
    assert e.team is None


def test_event_survivor_winner_team() -> None:
    log_event = LogEvent(events.SurvivorWinner, data="Red")
    e = events.SurvivorWinner.from_log_event(log_event)
    assert e.slot is None
    assert e.team == Team.RED


def test_event_team_scores() -> None:
    log_event = LogEvent(events.TeamScores, data="red:8  blue:5")
    e = events.TeamScores.from_log_event(log_event)
    assert e.red == 8
    assert e.blue == 5


def test_event_thaw_out_finished() -> None:
    log_event = LogEvent(
        events.ThawOutFinished,
        data="4 13: |30+|money^7 thawed out I30+IColombianRipper^7",
    )
    e = events.ThawOutFinished.from_log_event(log_event)
    assert e.slot == "4"
    assert e.target == "13"


def test_event_thaw_out_started() -> None:
    log_event = LogEvent(
        events.ThawOutStarted,
        data="4 9: |30+|money^7 started thawing out |30+|hedgehog^7",
    )
    e = events.ThawOutStarted.from_log_event(log_event)
    assert e.slot == "4"
    assert e.target == "9"
