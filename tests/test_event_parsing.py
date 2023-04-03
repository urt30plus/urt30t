import pytest

from urt30t import parser
from urt30t.models import Event, EventType


@pytest.mark.parametrize(
    ("log_line", "event"),
    [
        (
            "  3:01 Bomb has been dropped by 2",
            Event(EventType.bomb, "3:01", data={"action": "dropped"}, client="2"),
        ),
        (
            "  3:01 Bomb was placed by 2",
            Event(EventType.bomb, "3:01", data={"action": "placed"}, client="2"),
        ),
        ("  3:01 Bombholder is 2", Event(EventType.bomb_holder, "3:01", client="2")),
        ("  3:02 ClientSpawn: 8", Event(EventType.client_spawn, "3:02", client="8")),
        (
            "  0:58 Flag Return: BLUE",
            Event(EventType.flag_return, "0:58", data={"team": "BLUE"}),
        ),
        (
            "  3:01 Session data initialised for client on slot 0 at 203293239",
            Event(
                EventType.session_data_initialised,
                "3:01",
                data={"raw": "0 at 203293239"},
            ),
        ),
        (
            "  3:01 ------------------------------------------------------",
            Event(EventType.log_separator, "3:01"),
        ),
        (
            "  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)",
            Event(
                EventType.say_team,
                "0:28",
                data={"text": "|30+|money: $gameitem dropped (^1$hp^3/hp)"},
                client="0",
            ),
        ),
        ("  0:00 Warmup:", Event(EventType.warmup, "0:00")),
        (
            "  3:02 FooBar: this is not a real event",
            Event(
                EventType.unknown, "3:02", {"raw": "FooBar: this is not a real event"}
            ),
        ),
    ],
)
def test_log_event_parsing(log_line, event):
    e = parser.from_log_line(log_line)
    assert e == event
