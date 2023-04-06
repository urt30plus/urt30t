import dataclasses
from typing import NamedTuple, Self

from .models import Team


class LogEvent(NamedTuple):
    type: str | None = None
    game_time: str = "00:00"
    data: str = ""


@dataclasses.dataclass
class GameEvent:
    game_time: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        return cls(game_time=log_event.game_time)


@dataclasses.dataclass
class SlotGameEvent(GameEvent):
    slot: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        return cls(game_time=log_event.game_time, slot=log_event.data)


@dataclasses.dataclass
class AccountKick(GameEvent):
    pass


@dataclasses.dataclass
class AccountRejected(GameEvent):
    pass


@dataclasses.dataclass
class AccountValidated(GameEvent):
    slot: str
    auth: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        slot, auth, text = log_event.data.split(" - ", maxsplit=2)
        return cls(game_time=log_event.game_time, slot=slot, auth=auth, text=text)


@dataclasses.dataclass
class Assist(GameEvent):
    pass


@dataclasses.dataclass
class Bomb(GameEvent):
    slot: str
    # TODO: BombAction enum?
    action: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        parts = log_event.data.split(" ")
        return cls(game_time=log_event.game_time, slot=parts[2], action=parts[0])


@dataclasses.dataclass
class BombHolder(GameEvent):
    pass


@dataclasses.dataclass
class CallVote(GameEvent):
    pass


@dataclasses.dataclass
class ClientBegin(SlotGameEvent):
    pass


@dataclasses.dataclass
class ClientConnect(SlotGameEvent):
    slot: str


@dataclasses.dataclass
class ClientDisconnect(SlotGameEvent):
    slot: str


@dataclasses.dataclass
class ClientMelted(GameEvent):
    pass


@dataclasses.dataclass
class ClientSpawn(SlotGameEvent):
    slot: str


@dataclasses.dataclass
class ClientUserInfo(GameEvent):
    slot: str
    user_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        slot, _, text = log_event.data.partition(" ")
        data = _parse_info_string(text)
        return cls(game_time=log_event.game_time, slot=slot, user_data=data)


@dataclasses.dataclass
class ClientUserinfoChanged(ClientUserInfo):
    pass


@dataclasses.dataclass
class Exit(GameEvent):
    pass


@dataclasses.dataclass
class Flag(GameEvent):
    pass


@dataclasses.dataclass
class FlagCaptureTime(GameEvent):
    pass


@dataclasses.dataclass
class FlagReturn(GameEvent):
    team: Team

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        return cls(game_time=log_event.game_time, team=Team[log_event.data])


@dataclasses.dataclass
class Freeze(GameEvent):
    pass


@dataclasses.dataclass
class Hit(GameEvent):
    pass


@dataclasses.dataclass
class HotPotato(GameEvent):
    pass


@dataclasses.dataclass
class InitAuth(GameEvent):
    pass


@dataclasses.dataclass
class InitGame(GameEvent):
    game_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        return cls(
            game_time=log_event.game_time, game_data=_parse_info_string(log_event.data)
        )


@dataclasses.dataclass
class InitRound(GameEvent):
    pass


@dataclasses.dataclass
class Item(GameEvent):
    pass


@dataclasses.dataclass
class Kill(GameEvent):
    pass


@dataclasses.dataclass
class Pop(GameEvent):
    pass


@dataclasses.dataclass
class Radio(GameEvent):
    pass


@dataclasses.dataclass
class Score(GameEvent):
    pass


@dataclasses.dataclass
class Say(GameEvent):
    slot: str
    name: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        slot, text = log_event.data.split(" ", maxsplit=1)
        name, text = text.split(": ", maxsplit=1)
        return cls(game_time=log_event.game_time, slot=slot, name=name, text=text)


@dataclasses.dataclass
class SayTeam(Say):
    pass


@dataclasses.dataclass
class SayTell(Say):
    target: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        slot, target, text = log_event.data.split(" ", maxsplit=2)
        name, text = text.split(": ", maxsplit=1)
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            target=target,
            name=name,
            text=text,
        )


@dataclasses.dataclass
class SessionDataInitialised(GameEvent):
    pass


@dataclasses.dataclass
class ShutdownGame(GameEvent):
    pass


@dataclasses.dataclass
class Vote(GameEvent):
    pass


@dataclasses.dataclass
class VoteFailed(GameEvent):
    pass


@dataclasses.dataclass
class VotePassed(GameEvent):
    pass


@dataclasses.dataclass
class Warmup(GameEvent):
    pass


def _parse_info_string(data: str) -> dict[str, str]:
    parts = data.lstrip("\\").split("\\")
    return dict(zip(parts[0::2], parts[1::2], strict=True))
