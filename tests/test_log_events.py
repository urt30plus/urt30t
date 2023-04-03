from urt30t import events


def test_parse_warmup():
    e = events.from_log_line("0:00 Warmup:")
    assert e.game_time == "0:00"
    assert e.event_type == events.EventType.warmup
    assert e.data == ""


def test_parse_client_spawn():
    e = events.from_log_line("3:02 ClientSpawn: 9")
    assert e.game_time == "3:02"
    assert e.event_type == events.EventType.client_spawn
    assert e.data == "9"


def test_parse_session_init():
    e = events.from_log_line(
        "3:01 Session data initialised for client on slot 0 at 203293239"
    )
    assert e.event_type == events.EventType.session_data_initialised
    assert e.data == "0 at 203293239"


def test_parse_log_separator():
    e = events.from_log_line(
        "3:01 ------------------------------------------------------"
    )
    assert e.event_type == events.EventType.log_separator
    assert e.data == ""


def test_parse_bomb_holder():
    e = events.from_log_line("3:01 Bombholder is 2")
    assert e.event_type == events.EventType.bomb_holder
    assert e.data == "2"


def test_parse_bomb_placed():
    e = events.from_log_line("3:01 Bomb was placed by 2")
    assert e.event_type == events.EventType.bomb
    assert e.data == "placed by 2"


def test_parse_bomb_dropped():
    e = events.from_log_line("3:01 Bomb has been dropped by 2")
    assert e.event_type == events.EventType.bomb
    assert e.data == "dropped by 2"


def test_parse_flag_return():
    e = events.from_log_line("  0:58 Flag Return: BLUE")
    assert e.event_type == events.EventType.flag_return
    assert e.data == "BLUE"


def test_parse_say_team():
    e = events.from_log_line(
        "  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)"
    )
    assert e.event_type == events.EventType.say_team
    assert e.data == "0 |30+|money: $gameitem dropped (^1$hp^3/hp)"


def test_parse_unknown_event():
    e = events.from_log_line("  3:02 FooBar: this is not a real event")
    assert e.event_type is events.EventType.unknown
    assert e.data == "FooBar: this is not a real event"
