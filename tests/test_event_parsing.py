import pytest

from urt30t import parser
from urt30t.models import EventType, LogEvent


@pytest.mark.parametrize(
    ("log_line", "log_event"),
    [
        (
            "  3:01 Bomb has been dropped by 2",
            LogEvent(EventType.bomb, "3:01", data="dropped by 2"),
        ),
        (
            "  3:01 Bomb was placed by 2",
            LogEvent(EventType.bomb, "3:01", "placed by 2"),
        ),
        ("  3:01 Bombholder is 2", LogEvent(EventType.bomb_holder, "3:01", "2")),
        ("  3:02 ClientSpawn: 8", LogEvent(EventType.client_spawn, "3:02", "8")),
        (
            "  0:58 Flag Return: BLUE",
            LogEvent(EventType.flag_return, "0:58", "BLUE"),
        ),
        (
            "  3:01 Session data initialised for client on slot 0 at 203293239",
            LogEvent(
                EventType.session_data_initialised,
                "3:01",
                "0 at 203293239",
            ),
        ),
        (
            "  3:01 ------------------------------------------------------",
            LogEvent(EventType.log_separator, "3:01", ""),
        ),
        (
            "  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            LogEvent(
                EventType.say_team,
                "0:28",
                "0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            ),
        ),
        ("  0:00 Warmup:", LogEvent(EventType.warmup, "0:00", "")),
        (
            "  3:02 FooBar: this is not a real event",
            LogEvent(EventType.unknown, "3:02", "FooBar: this is not a real event"),
        ),
    ],
)
def test_log_event_parsing(log_line, log_event):
    e = parser.from_log_line(log_line)
    assert e == log_event
