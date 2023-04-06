import pytest

from urt30t.core import parse_log_line
from urt30t.events import LogEvent


@pytest.mark.parametrize(
    ("log_line", "log_event"),
    [
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
    ],
)
def test_log_event_parsing(log_line, log_event):
    e = parse_log_line(log_line)
    assert e == log_event
