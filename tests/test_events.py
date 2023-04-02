from urt30t import events


def test_parse_client_spawn():
    e = events.from_log_line("3:02 ClientSpawn: 9")
    assert e.game_time == "3:02"
    assert e.event_type == events.EventType.client_spawn
