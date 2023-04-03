import pytest

from urt30t import parser
from urt30t.models import EventType


@pytest.mark.parametrize(
    ("log_line", "event_type", "data"),
    [
        ("  3:01 Bomb has been dropped by 2", EventType.bomb, "dropped by 2"),
        ("  3:01 Bomb was placed by 2", EventType.bomb, "placed by 2"),
        ("  3:01 Bombholder is 2", EventType.bomb_holder, "2"),
        ("  3:02 ClientSpawn: 8", EventType.client_spawn, "8"),
        ("  0:58 Flag Return: BLUE", EventType.flag_return, "BLUE"),
        (
            "  3:01 Session data initialised for client on slot 0 at 203293239",
            EventType.session_data_initialised,
            "0 at 203293239",
        ),
        (
            "  3:01 ------------------------------------------------------",
            EventType.log_separator,
            "",
        ),
        (
            "  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            EventType.say_team,
            "0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
        ),
        ("  0:00 Warmup:", EventType.warmup, ""),
        (
            "  3:02 FooBar: this is not a real event",
            EventType.unknown,
            "FooBar: this is not a real event",
        ),
    ],
)
def test_log_event_parsing(log_line, event_type, data):
    e = parser.from_log_line(log_line)
    assert e.event_type is event_type
    assert e.data == data
