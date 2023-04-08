from urt30t import events
from urt30t.events import LogEvent
from urt30t.models import KillMode


def test_event_account_kick():
    log_event = LogEvent(
        type="accountkick", data="13 - [ABC]foobar^7 rejected: no account"
    )
    e = events.AccountKick.from_log_event(log_event)
    assert e.slot == "13"
    assert e.name == "[ABC]foobar"
    assert e.reason == "no account"


def test_event_account_rejected():
    log_event = LogEvent(type="accountrejected", data='19 -  - "no account"')
    e = events.AccountRejected.from_log_event(log_event)
    assert e.slot == "19"


def test_event_assist():
    log_event = LogEvent(
        "assist", data="12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7"
    )
    e = events.Assist.from_log_event(log_event)
    assert e.slot == "12"
    assert e.killer == "1"
    assert e.victim == "0"


def test_event_team_scores():
    log_event = LogEvent("red", data="red:8  blue:5")
    e = events.TeamScores.from_log_event(log_event)
    assert e.red == 8
    assert e.blue == 5


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
