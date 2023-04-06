import pytest

from urt30t import events
from urt30t.core import parse_log_line
from urt30t.events import LogEvent


@pytest.mark.parametrize(
    ("log_line", "log_event"),
    [
        (
            "2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account",
            LogEvent("accountkick", "2:34", "13 - [ABC]foobar^7 rejected: no account"),
        ),
        (
            "  3:01 Bomb has been dropped by 2",
            LogEvent("bomb", "3:01", "dropped by 2"),
        ),
        (
            "  3:01 Bomb was placed by 2",
            LogEvent("bomb", "3:01", "placed by 2"),
        ),
        ("  3:01 Bombholder is 2", LogEvent("bombholder", "3:01", "2")),
        ("  3:02 ClientSpawn: 8", LogEvent("clientspawn", "3:02", "8")),
        (
            "  0:58 Flag Return: BLUE",
            LogEvent("flagreturn", "0:58", "BLUE"),
        ),
        (
            "  3:01 Session data initialised for client on slot 0 at 203293239",
            LogEvent(
                "sessiondatainitialised",
                "3:01",
                "0 at 203293239",
            ),
        ),
        (
            "  3:01 ------------------------------------------------------",
            LogEvent(None, "3:01", ""),
        ),
        (
            "  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            LogEvent(
                "sayteam",
                "0:28",
                "0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            ),
        ),
        ("  0:00 Warmup:", LogEvent("warmup", "0:00", "")),
        (
            "  3:02 FooBar: this is not a real event",
            LogEvent("foobar", "3:02", "this is not a real event"),
        ),
        (
            " 15:22 red:8  blue:5",
            LogEvent("teamscores", "15:22", "red:8  blue:5"),
        ),
    ],
)
def test_log_event_parsing(log_line, log_event):
    e = parse_log_line(log_line)
    assert e == log_event


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
