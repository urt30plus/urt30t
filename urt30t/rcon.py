import asyncio
import logging
import re
import textwrap
from asyncio.transports import DatagramTransport
from pathlib import Path
from typing import Any, NamedTuple, TypedDict, cast

logger = logging.getLogger(__name__)

_CMD_PREFIX = b"\xff" * 4
_REPLY_PREFIX = _CMD_PREFIX + b"print\n"
_ENCODING = "latin-1"
_MAX_MESSAGE_LENGTH = 80

_CVAR_PATTERNS = (
    # "sv_maxclients" is:"16^7" default:"8^7"
    # latched: "12"  # noqa: ERA001
    re.compile(
        r'^"(?P<cvar>[a-z0-9_.]+)"\s+is:\s*'
        r'"(?P<value>.*?)(\^7)?"\s+default:\s*'
        r'"(?P<default>.*?)(\^7)?"$',
        re.IGNORECASE | re.MULTILINE,
    ),
    # "g_maxGameClients" is:"0^7", the default
    # latched: "1"  # noqa: ERA001
    re.compile(
        r'^"(?P<cvar>[a-z0-9_.]+)"\s+is:\s*'
        r'"(?P<default>(?P<value>.*?))(\^7)?",\s+the\sdefault$',
        re.IGNORECASE | re.MULTILINE,
    ),
    # "mapname" is:"ut4_abbey^7"
    re.compile(
        r'^"(?P<cvar>[a-z0-9_.]+)"\s+is:\s*"(?P<value>.*?)(\^7)?"$',
        re.IGNORECASE | re.MULTILINE,
    ),
)

RE_COLOR = re.compile(r"(\^\d)")

RE_SCORES = re.compile(r"\s*R:(?P<red>\d+)\s+B:(?P<blue>\d+)")

_RE_PLAYER = re.compile(
    r"^(?P<slot>[0-9]+):(?P<name>.*)\s+"
    r"TEAM:(?P<team>RED|BLUE|SPECTATOR|FREE)\s+"
    r"KILLS:(?P<kills>-?[0-9]+)\s+"
    r"DEATHS:(?P<deaths>[0-9]+)\s+"
    r"ASSISTS:(?P<assists>[0-9]+)\s+"
    r"PING:(?P<ping>[0-9]+|CNCT|ZMBI)\s+"
    r"AUTH:(?P<auth>.*)\s+"
    r"IP:(?P<ip_address>.*)$",
    re.IGNORECASE,
)

_TEAM_NAMES = ("red", "r", "blue", "b", "spectator", "spec", "s")


class _Protocol(asyncio.DatagramProtocol):
    def __init__(
        self, recv_q: asyncio.Queue[bytes], buffer_free: asyncio.Event
    ) -> None:
        buffer_free.set()
        self._recv_q = recv_q
        self._buffer_free = buffer_free
        self._transport: DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        logger.debug(transport)
        self._transport = cast(DatagramTransport, transport)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc is None:
            logger.info("Connection closed")
        else:
            logger.error("Connection closed: %r", exc)
        if size := self._recv_q.qsize():
            logger.warning("Receive queue has pending items: %s", size)
        if self._transport:
            self._transport.close()

    def datagram_received(self, data: bytes, _: tuple[str | Any, int]) -> None:
        logger.debug(data)
        self._recv_q.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        self.connection_lost(exc)

    def pause_writing(self) -> None:
        logger.warning("pausing writes")
        self._buffer_free.clear()

    def resume_writing(self) -> None:
        logger.warning("resuming writes")
        self._buffer_free.set()


class Cvar(NamedTuple):
    name: str
    value: str
    default: str | None = None


class Player(TypedDict):
    slot: str
    name: str
    team: str
    kills: int
    deaths: int
    assists: int
    ping: str
    auth: str
    ip_address: str


class Game(TypedDict):
    Map: str
    Players: int
    GameType: str
    Scores: str
    MatchMode: bool
    WarmupPhase: bool
    GameTime: str
    Slots: list[Player]


class RconClient:
    def __init__(
        self,
        host: str,
        port: int,
        password: bytes,
        transport: DatagramTransport,
        recv_q: asyncio.Queue[bytes],
        recv_timeout: float,
        buffer_free: asyncio.Event,
    ) -> None:
        self.host = host
        self.port = port
        self._password = password
        self._transport = transport
        self._recv_q = recv_q
        self._recv_timeout = recv_timeout
        self._buffer_free = buffer_free
        self._lock = asyncio.Lock()

    async def bigtext(self, message: str, prefix: str = "") -> None:
        await self.message(message, prefix=prefix, kind="bigtext")

    async def broadcast(self, message: str, prefix: str = "") -> None:
        await self.message(message, prefix=prefix, kind="")

    def close(self) -> None:
        self._transport.close()

    async def cvar(self, name: str) -> Cvar | None:
        if not (data := await self._execute(name, retry=True)):
            return None

        cvar = data.decode(encoding=_ENCODING)
        for pat in _CVAR_PATTERNS:
            if m := pat.match(cvar):
                break
        else:
            return None

        if m["cvar"].lower() != name.lower():
            logger.warning("cvar sent [%s], received [%s]", name, m["cvar"])
            return None

        try:
            default = m["default"]
        except IndexError:
            default = None

        return Cvar(name=name, value=m["value"], default=default)

    async def cvarlist(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not (data := await self._execute(f"cvarlist {prefix}", multi_recv=True)):
            return result
        items = data.decode(encoding=_ENCODING).splitlines()
        for cv in items[:-3]:
            if item := cv[8:].strip():
                name, _, value = item.partition(' "')
                result[name] = value.removesuffix('"')
        return result

    async def cycle_map(self) -> None:
        await self._execute(b"cyclemap")

    async def force(self, slot: str, team: str) -> None:
        if (target := team.lower()) not in _TEAM_NAMES:
            raise ValueError(team)
        await self._execute(f"forceteam {slot} {target}")

    async def map_restart(self) -> None:
        await self._execute(b"map_restart")

    async def mapcycle_file(self) -> Path | None:
        if fs_data := await self.cvarlist("fs_"):
            base_path = Path(fs_data["fs_homepath"]) / fs_data["fs_game"]
            if map_file := await self.cvar("g_mapcycle"):
                return base_path / map_file.value
        return None

    async def maps(self) -> list[str]:
        if not (
            data := await self._execute(b"fdir *.bsp", retry=True, multi_recv=True)
        ):
            logger.error("command returned no data")
            return []
        lines = data.decode(encoding=_ENCODING).splitlines()
        if (
            len(lines) < 2
            or not lines[0].startswith("-----")
            or not lines[-1].endswith("files listed")
        ):
            logger.error("invalid response: %r", lines)
            return []
        return [x.removeprefix("maps/").removesuffix(".bsp") for x in lines[1:-1]]

    async def message(self, message: str, prefix: str = "", kind: str = "say") -> None:
        if kind and not kind.endswith(" "):
            kind += " "
        width = _MAX_MESSAGE_LENGTH - len(prefix)
        for line in _wrap_message(message, width):
            await self._execute(f'{kind}"{prefix}{line}"')
            await asyncio.sleep(0.25)

    async def players(self) -> Game:
        """
        Map: ut4_abbey
        Players: 3
        GameType: CTF
        Scores: R:5 B:10
        MatchMode: OFF
        WarmupPhase: NO
        GameTime: 00:12:04
        0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1
        1:bar^7 TEAM:BLUE KILLS:20 DEATHS:9 ASSISTS:0 PING:98 AUTH:bar IP:127.0.0.1
        2:baz^7 TEAM:RED KILLS:32 DEATHS:18 ASSISTS:0 PING:98 AUTH:baz IP:127.0.0.1
        """
        if not (data := await self._execute(b"players", retry=True, multi_recv=True)):
            logger.error("players command returned no data")
            raise LookupError
        return _parse_players_command(data.decode(encoding=_ENCODING))

    async def private_message(self, slot: str, message: str, prefix: str = "") -> None:
        await self.message(message, prefix, f"tell {slot}")

    async def reload(self) -> None:
        await self._execute(b"reload")

    async def shuffle_teams(self) -> None:
        await self._execute(b"shuffleteams")

    async def swap_teams(self) -> None:
        await self._execute(b"swapteams")

    async def _execute(
        self, cmd: str | bytes, *, retry: bool = False, multi_recv: bool = False
    ) -> bytes | None:
        if isinstance(cmd, str):
            cmd = cmd.encode(encoding=_ENCODING)
        cmd = b'%srcon "%s" %s\n' % (_CMD_PREFIX, self._password, cmd)
        async with self._lock:
            # handle reconnects on case of errors or lost connections
            if self._transport.is_closing():
                self._transport = await _new_transport(
                    self.host, self.port, self._recv_q, self._buffer_free
                )
            self._transport.sendto(cmd)
            await self._buffer_free.wait()
            data = await self._recv()
            if multi_recv and data is not None:
                while more_data := await self._recv():
                    data += more_data

        if retry and data is None:
            return await self._execute(cmd, retry=False, multi_recv=multi_recv)

        return data

    async def _recv(self) -> bytes | None:
        try:
            data = await asyncio.wait_for(
                self._recv_q.get(), timeout=self._recv_timeout
            )
        except asyncio.TimeoutError:
            return None
        else:
            if data.startswith(_REPLY_PREFIX):
                return data[len(_REPLY_PREFIX) :]
            logger.warning("reply does not contain expected prefix: %r", data)
            return data

    def __repr__(self) -> str:
        return (
            f"RconClient(host={self._transport.get_extra_info('peername')}, "
            f"recv_timeout={self._recv_timeout})"
        )


def _wrap_message(message: str, width: int) -> list[str]:
    return [
        x.strip() for line in message.splitlines() for x in textwrap.wrap(line, width)
    ]


def _parse_players_player(data: str) -> Player:
    """
    0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1
    """
    if m := _RE_PLAYER.match(data.strip()):
        ip_addr, _, port = m["ip_address"].partition(":")
        return {
            "slot": m["slot"],
            "name": m["name"].removesuffix("^7"),
            "team": m["team"],
            "kills": int(m["kills"]),
            "deaths": int(m["deaths"]),
            "assists": int(m["assists"]),
            "ping": m["ping"],
            "auth": m["auth"],
            "ip_address": ip_addr,
        }

    raise ValueError(data)


def _parse_players_command(data: str) -> Game:
    """
    Map: ut4_abbey
    Players: 3
    GameType: CTF
    Scores: R:5 B:10
    MatchMode: OFF
    WarmupPhase: NO
    GameTime: 00:12:04
    0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1
    """
    in_header = True
    game: Game = {}  # type: ignore[typeddict-item]
    players = []
    for line in data.splitlines():
        k, v = line.split(":", maxsplit=1)
        v = v.strip()
        if in_header:
            if k == "Map":
                game["Map"] = v
            elif k == "Players":
                game["Players"] = int(v)
            elif k == "GameType":
                game["GameType"] = v
            elif k == "Scores":
                game["Scores"] = v
            elif k == "MatchMode":
                game["MatchMode"] = v != "OFF"
            elif k == "WarmupPhase":
                game["WarmupPhase"] = v != "NO"
            elif k == "GameTime":
                game["GameTime"] = v
                in_header = False
            else:
                logger.warning("unknown header: %s - %s", k, v)
        elif k.isnumeric():
            players.append(_parse_players_player(line))
        elif k == "Map":
            # back-to-back messages, start over
            game["Map"] = v
            in_header = True

    game["Slots"] = players
    return game


async def create_client(
    host: str, port: int, password: str, recv_timeout: float = 0.2
) -> RconClient:
    recv_q = asyncio.Queue[bytes]()
    buffer_free = asyncio.Event()
    transport = await _new_transport(host, port, recv_q, buffer_free)
    return RconClient(
        host,
        port,
        password.encode(encoding=_ENCODING),
        transport,
        recv_q,
        recv_timeout,
        buffer_free,
    )


async def _new_transport(
    host: str, port: int, recv_q: asyncio.Queue[bytes], buffer_free: asyncio.Event
) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Protocol(recv_q, buffer_free), remote_addr=(host, port)
    )
    return transport
