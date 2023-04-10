from urt30t import events
from urt30t.events import LogEvent
from urt30t.models import BombAction, KillMode


def test_event_account_kick():
    log_event = LogEvent(
        type="accountkick", data="13 - [ABC]foobar^7 rejected: no account"
    )
    e = events.AccountKick.from_log_event(log_event)
    assert e.slot == "13"
    assert e.text == "[ABC]foobar^7 rejected: no account"


def test_event_account_rejected():
    log_event = LogEvent(type="accountrejected", data='19 -  - "no account"')
    e = events.AccountRejected.from_log_event(log_event)
    assert e.slot == "19"
    assert e.text == '-  - "no account"'


def test_event_account_validated():
    log_event = LogEvent(type="accountvalidated", data='0 - m0neysh0t - 6 - ""')
    e = events.AccountValidated.from_log_event(log_event)
    assert e.slot == "0"
    assert e.auth == "m0neysh0t"


def test_event_assist():
    log_event = LogEvent(
        "assist", data="12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7"
    )
    e = events.Assist.from_log_event(log_event)
    assert e.slot == "12"
    assert e.killer == "1"
    assert e.victim == "0"


def test_event_bomb_defused():
    log_event = LogEvent("bomb", data="defused by 11!")
    e = events.Bomb.from_log_event(log_event)
    assert e.slot == "11"
    assert e.action is BombAction.DEFUSED


def test_event_bomb_tossed():
    log_event = LogEvent("bomb", data="tossed by 8")
    e = events.Bomb.from_log_event(log_event)
    assert e.slot == "8"
    assert e.action is BombAction.TOSSED


def test_event_bomb_holder():
    log_event = LogEvent("bombholder", data="2")
    e = events.BombHolder.from_log_event(log_event)
    assert e.slot == "2"


def test_event_client_begin():
    log_event = LogEvent("clientbegin", data="4")
    e = events.ClientBegin.from_log_event(log_event)
    assert e.slot == "4"


def test_event_client_connect():
    log_event = LogEvent("clientconnect", data="15")
    e = events.ClientBegin.from_log_event(log_event)
    assert e.slot == "15"


def test_event_client_disconnect():
    log_event = LogEvent("clientdisconnect", data="15")
    e = events.ClientDisconnect.from_log_event(log_event)
    assert e.slot == "15"


def test_event_client_spawn():
    log_event = LogEvent("clientspawn", data="15")
    e = events.ClientSpawn.from_log_event(log_event)
    assert e.slot == "15"


def test_event_flag_capture_time():
    log_event = LogEvent("flagcapturetime", data="0: 15750")
    e = events.FlagCaptureTime.from_log_event(log_event)
    assert e.slot == "0"
    assert e.cap_time == 15.75


def test_event_kill():
    log_event = LogEvent(
        "kill", data="8 5 46: |30+|Mudcat^7 killed |30+|BenderBot^7 by UT_MOD_TOD50"
    )
    e = events.Kill.from_log_event(log_event)
    assert e.slot == "8"
    assert e.victim == "5"
    assert e.kill_mode is KillMode.TOD50


def test_event_team_scores():
    log_event = LogEvent("red", data="red:8  blue:5")
    e = events.TeamScores.from_log_event(log_event)
    assert e.red == 8
    assert e.blue == 5
