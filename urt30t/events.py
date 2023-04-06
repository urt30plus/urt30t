import dataclasses
from typing import Self


class Event:
    @classmethod
    def from_string(cls, data: str) -> Self:
        if not data:
            return cls()
        raise NotImplementedError


@dataclasses.dataclass
class ClientBegin(Event):
    slot: str

    @classmethod
    def from_string(cls, data: str) -> Self:
        return cls(slot=data)


@dataclasses.dataclass
class InitGame(Event):
    data: dict[str, str]

    @classmethod
    def from_string(cls, data: str) -> Self:
        return cls(_parse_info_string(data))


@dataclasses.dataclass
class Warmup(Event):
    pass


def _parse_info_string(data: str) -> dict[str, str]:
    parts = data.lstrip("\\").split("\\")
    return dict(zip(parts[0::2], parts[1::2], strict=True))
