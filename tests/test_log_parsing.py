from urt30t import events
from urt30t.events import parse_log_line


def test_log_account_kick() -> None:
    e = parse_log_line("  2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account")
    assert e
    assert e.kind is events.AccountKick
    assert e.data == "13 - [ABC]foobar^7 rejected: no account"


def test_log_bomb_dropped() -> None:
    e = parse_log_line("  3:01 Bomb has been dropped by 2")
    assert e
    assert e.kind is events.Bomb
    assert e.data == "dropped by 2"


def test_log_bomb_difused() -> None:
    e = parse_log_line("  6:52 Bomb was defused by 11!")
    assert e
    assert e.kind is events.Bomb
    assert e.data == "defused by 11!"


def test_log_bomb_holder() -> None:
    e = parse_log_line("  3:01 Bombholder is 2")
    assert e
    assert e.kind is events.BombHolder
    assert e.data == "2"


def test_log_bomb_explode() -> None:
    e = parse_log_line("  3:02 Pop!")
    assert e
    assert e.kind is events.Pop
    assert not e.data


def test_log_client_spawn() -> None:
    e = parse_log_line("  3:02 ClientSpawn: 8")
    assert e
    assert e.kind is events.ClientSpawn
    assert e.data == "8"


def test_log_flag_return() -> None:
    e = parse_log_line("  0:58 Flag Return: BLUE")
    assert e
    assert e.kind is events.FlagReturn
    assert e.data == "BLUE"


def test_log_session_data_init() -> None:
    e = parse_log_line(
        "  3:01 Session data initialised for client on slot 0 at 203293239"
    )
    assert e is None


def test_log_separator() -> None:
    e = parse_log_line("  3:01 ------------------------------------------------------")
    assert e is None


def test_log_say_team() -> None:
    e = parse_log_line("  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)")
    assert e
    assert e.kind is events.SayTeam
    assert e.data == "0 |30+|money: $gameitem dropped (^1$hp^3/hp)"


def test_log_warmup() -> None:
    e = parse_log_line("  0:00 Warmup:")
    assert e
    assert e.kind is events.Warmup
    assert not e.data


def test_log_teams_scores() -> None:
    e = parse_log_line(" 15:22 red:8  blue:5")
    assert e
    assert e.kind is events.TeamScores
    assert e.data == "red:8  blue:5"


def test_log_survivor_winner() -> None:
    e = parse_log_line("11403:1SurvivorWinner: Red")
    assert e
    assert e.kind is events.SurvivorWinner
    assert e.data == "Red"


def test_log_no_type() -> None:
    e = parse_log_line(" 12:33 no type found")
    assert e is None


def test_log_long_event_time() -> None:
    e = parse_log_line("1687:13ClientConnect: 8")
    assert e
    assert e.kind is events.ClientConnect
    assert e.event_time == "1687:13"
    assert e.data == "8"
