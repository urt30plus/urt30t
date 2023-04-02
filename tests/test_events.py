from urt30t import events


def test_parse_client_spawn():
    e = events.from_log_line("3:02 ClientSpawn: 9")
    assert e.game_time == "3:02"
    assert e.event_type == events.EventType.client_spawn


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
    assert e.data is None


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
