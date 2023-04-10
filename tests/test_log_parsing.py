from urt30t.core import parse_log_line


def test_log_account_kick():
    e = parse_log_line("2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account")
    assert e.type == "accountkick"
    assert e.data == "13 - [ABC]foobar^7 rejected: no account"


def test_log_bomb_dropped():
    e = parse_log_line("  3:01 Bomb has been dropped by 2")
    assert e.type == "bomb"
    assert e.data == "dropped by 2"


def test_log_bomb_difused():
    e = parse_log_line(" 6:52 Bomb was defused by 11!")
    assert e.type == "bomb"
    assert e.data == "defused by 11!"


def test_log_bomb_holder():
    e = parse_log_line("  3:01 Bombholder is 2")
    assert e.type == "bombholder"
    assert e.data == "2"


def test_log_bomb_explode():
    e = parse_log_line("  3:02 Pop!")
    assert e.type == "pop"
    assert e.data == ""


def test_log_client_spawn():
    e = parse_log_line("  3:02 ClientSpawn: 8")
    assert e.type == "clientspawn"
    assert e.data == "8"


def test_log_flag_return():
    e = parse_log_line("  0:58 Flag Return: BLUE")
    assert e.type == "flagreturn"
    assert e.data == "BLUE"


def test_log_session_data_init():
    e = parse_log_line(
        "  3:01 Session data initialised for client on slot 0 at 203293239"
    )
    assert e.type is None
    assert e.data == "Session data initialised for client on slot 0 at 203293239"


def test_log_separator():
    e = parse_log_line("  3:01 ------------------------------------------------------")
    assert e.type is None
    assert e.data == ""


def test_log_say_team():
    e = parse_log_line("  0:28 sayteam: 0 |30+|money: $gameitem dropped (^1$hp^3/hp)")
    assert e.type == "sayteam"
    assert e.data == "0 |30+|money: $gameitem dropped (^1$hp^3/hp)"


def test_log_warmup():
    e = parse_log_line("  0:00 Warmup:")
    assert e.type == "warmup"
    assert e.data == ""


def test_log_teams_scores():
    e = parse_log_line(" 15:22 red:8  blue:5")
    assert e.type == "teamscores"
    assert e.data == "red:8  blue:5"


def test_log_no_type():
    e = parse_log_line(" 12:33 no type found")
    assert e.type is None
    assert e.data == "no type found"
