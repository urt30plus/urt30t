from textwrap import dedent

from urt30arcon import Game, GameType, Player, Team


def test_player_from_string():
    s = """\
    0:foo^7 TEAM:RED KILLS:20 DEATHS:22 ASSISTS:3 PING:98 AUTH:foo IP:127.0.0.1:58537
    """
    player = Player.from_string(dedent(s))
    assert player.name == "foo"
    assert player.team is Team.RED
    assert player.kills == 20
    assert player.deaths == 22
    assert player.assists == 3


def test_negative_kills():
    s = """\
    0:foo^7 TEAM:RED KILLS:-1 DEATHS:2 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1:58537
    """
    player = Player.from_string(dedent(s))
    assert player.name == "foo"
    assert player.team is Team.RED
    assert player.kills == -1
    assert player.deaths == 2
    assert player.assists == 0


def test_game_from_string_ctf():
    s = """\
    Map: ut4_abbey
    Players: 3
    GameType: CTF
    Scores: R:5 B:10
    MatchMode: OFF
    WarmupPhase: NO
    GameTime: 00:12:04
    0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1:58537
    1:bar^7 TEAM:BLUE KILLS:20 DEATHS:9 ASSISTS:0 PING:98 AUTH:bar IP:127.0.0.1:58538
    2:baz^7 TEAM:RED KILLS:32 DEATHS:18 ASSISTS:0 PING:98 AUTH:baz IP:127.0.0.1:58539
    """
    game = Game.from_string(dedent(s))
    assert game.map_name == "ut4_abbey"
    assert game.type is GameType.CTF
    assert game.score_red == 5
    assert game.score_blue == 10
    assert game.time == "00:12:04"
    assert len(game.players) == 3


def test_from_string_ffa():
    s = """\
    Map: ut4_docks
    Players: 3
    GameType: FFA
    MatchMode: OFF
    WarmupPhase: NO
    GameTime: 00:12:04
    0:foo^7 TEAM:FREE KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1:0
    1:bar^7 TEAM:FREE KILLS:20 DEATHS:9 ASSISTS:0 PING:98 AUTH:bar IP:127.0.0.1:0
    2:baz^7 TEAM:FREE KILLS:32 DEATHS:18 ASSISTS:0 PING:98 AUTH:baz IP:127.0.0.1:0
    """
    game = Game.from_string(dedent(s))
    assert game.map_name == "ut4_docks"
    assert game.type is GameType.FFA
    assert game.score_red == 0
    assert game.score_blue == 0
    assert game.time == "00:12:04"
    assert len(game.players) == 3
