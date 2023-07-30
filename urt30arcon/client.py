import asyncio
import logging
import textwrap
from asyncio.transports import DatagramTransport
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Self, cast

from .models import AuthWhois, Cvar, Game, RconError, ServerStatus
from .protocol import _Protocol

logger = logging.getLogger(__name__)

_CMD_PREFIX = b"\xff" * 4
_REPLY_PREFIX = _CMD_PREFIX + b"print\n"
_ENCODING = "latin-1"
_MAX_MESSAGE_LENGTH = 80
_TEAM_NAMES = ("red", "r", "blue", "b", "spectator", "spec", "s")


class AsyncRconClient:
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
        self._tasks: set[asyncio.Task[None]] = set()

    async def auth_whois(self, slot: str) -> AuthWhois:
        if data := await self._execute(f"auth-whois {slot}"):
            return AuthWhois.from_string(data.decode(_ENCODING))
        raise RconError(slot)

    async def ban(self, ip_address: str) -> None:
        await self._execute(f"addip {ip_address}")

    async def bigtext(self, message: str) -> None:
        await self._send_message(message, kind="bigtext")

    async def broadcast(self, message: str) -> None:
        await self._send_message(message, kind="")

    def close(self) -> None:
        self._transport.close()

    async def cvar(self, name: str) -> Cvar | None:
        if not (data := await self._execute(name, retry=True)):
            return None
        return Cvar.from_string(data.decode(encoding=_ENCODING))

    async def cvarlist(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not (data := await self._execute(f"cvarlist {prefix}")):
            return result
        items = data.decode(encoding=_ENCODING).splitlines()
        for cv in items[:-3]:
            if item := cv[8:].strip():
                name, _, value = item.partition(' "')
                result[name] = value.removesuffix('"')
        return result

    async def cycle_map(self) -> None:
        await self._execute(b"cyclemap")

    async def dumpuser(self, slot: str) -> dict[str, str] | None:
        """
        /rcon dumpuser 0
        userinfo
        --------
        ip                  127.0.0.1:27961
        name                |30+|money
        authl               m0neysh0t
        cl_guid             E9A98F42280E5C2F072804F74029A050
        """
        cmd = f"dumpuser {slot}"
        if not (data := await self._execute(cmd)):
            return None
        userinfo = data.decode(_ENCODING)
        if not userinfo.startswith("userinfo"):
            logger.warning("%s: %s", cmd, userinfo)
            return None
        return {
            line[:20].strip(): line[20:].strip() for line in userinfo.splitlines()[2:]
        }

    async def force(self, slot: str, team: str) -> None:
        if (target := team.lower()) not in _TEAM_NAMES:
            raise ValueError(team)
        await self._execute(f"forceteam {slot} {target}")

    async def game_info(self) -> Game:
        data = await self.players()
        return Game.from_string(data)

    async def kick(self, slot: str, reason: str | None = None) -> None:
        cmd = f"kick {slot}"
        if reason:
            cmd += f' "{reason}"'
        await self._execute(cmd)

    async def kill(self, slot: str) -> None:
        await self._execute(f"smite {slot}")

    async def map_restart(self) -> None:
        await self._execute(b"map_restart")

    async def mapcycle_file(self) -> Path | None:
        if fs_data := await self.cvarlist("fs_"):
            base_path = Path(fs_data["fs_homepath"]) / fs_data["fs_game"]
            if map_file := await self.cvar("g_mapcycle"):
                return base_path / map_file.value
        return None

    async def map(self, map_name: str) -> None:  # noqa: A003
        await self._execute(f"map {map_name}")

    async def maps(self) -> list[str]:
        if not (data := await self._execute(b"fdir *.bsp", retry=True)):
            logger.error("maps command returned no data")
            return []
        lines = data.decode(encoding=_ENCODING).splitlines()
        if (
            len(lines) < 2  # noqa: PLR2004
            or not lines[0].startswith("-----")
            or not lines[-1].endswith("files listed")
        ):
            logger.error("invalid response: %r", lines)
            return []
        return [x.removeprefix("maps/").removesuffix(".bsp") for x in lines[1:-1]]

    async def mute(self, slot: str, duration: str | None = None) -> None:
        cmd = f"mute {slot}"
        if duration is not None:
            cmd += f" {_duration_to_seconds(duration)}"
        await self._execute(cmd)

    async def nuke(self, slot: str) -> None:
        await self._execute(f"nuke {slot}")

    async def pause(self) -> None:
        await self._execute(b"pause")

    async def players(self) -> str:
        if not (data := await self._execute(b"players", retry=True)):
            logger.error("players command returned no data")
            raise LookupError
        return data.decode(encoding=_ENCODING)

    async def say(self, message: str) -> None:
        await self._send_message(message, kind="say")

    async def tell(self, slot: str, message: str) -> None:
        await self._send_message(message, kind=f"tell {slot}")

    async def rcon(self, command: str, *, retry: bool = True) -> str:
        data = await self._execute(command, retry=retry)
        return data.decode(_ENCODING) if data is not None else ""

    async def reload(self) -> None:
        await self._execute(b"reload")

    async def serverinfo(self) -> dict[str, str]:
        """
        ]\rcon serverinfo
        Server info settings:
        sv_allowdownload    0
        g_matchmode         0
        g_gametype          7
        sv_maxclients       16
        ...
        """
        if data := await self._execute(b"serverinfo"):
            return {
                line[:20].strip(): line[20:].strip()
                for line in data.decode(_ENCODING).splitlines()[1:]
            }
        raise RconError

    async def setcvar(self, name: str, value: str) -> None:
        await self._execute(f"{name} {value}")

    async def shuffle_teams(self) -> None:
        await self._execute(b"shuffleteams")

    async def slap(self, slot: str) -> None:
        await self._execute(f"slap {slot}")

    async def status(self) -> ServerStatus:
        if data := await self._execute(b"status"):
            return ServerStatus.from_string(data.decode(_ENCODING))
        raise RconError

    async def swap_teams(self) -> None:
        await self._execute(b"swapteams")

    async def unban(self, ip_address: str) -> None:
        await self._execute(f"removeip {ip_address}")

    async def veto(self) -> None:
        await self._execute(b"veto")

    async def _send_message(self, message: str, kind: str) -> None:
        if kind and not kind.endswith(" "):
            kind += " "
        for line in _wrap_message(message, _MAX_MESSAGE_LENGTH):
            self._run_as_task(self._execute(f'{kind}"{line}"'))

    def _run_as_task(self, coro: Coroutine[Any, None, Any]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _execute(self, cmd: str | bytes, *, retry: bool = False) -> bytes | None:
        if isinstance(cmd, str):
            cmd = cmd.encode(encoding=_ENCODING)
        rcon_cmd = b'%srcon "%s" %s\n' % (_CMD_PREFIX, self._password, cmd)
        async with self._lock:
            # handle reconnects in case of errors or lost connections
            if self._transport.is_closing():
                self._transport = await _new_transport(
                    self.host, self.port, self._recv_q, self._buffer_free
                )
            self._transport.sendto(rcon_cmd)
            await self._buffer_free.wait()
            data = await self._recv()
            if data is not None:
                while more_data := await self._recv():
                    data += more_data

        if retry and data is None:
            logger.debug("retrying, no data received for command: %s", cmd)
            return await self._execute(cmd, retry=False)

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
                return data[len(_REPLY_PREFIX) :]  # noqa:RUF100,E203
            logger.warning("reply does not contain expected prefix: %r", data)
            return data

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"host={self.host}, port={self.port}, recv_timeout={self._recv_timeout})"
        )

    @classmethod
    async def create_client(
        cls, host: str, port: int, password: str, recv_timeout: float = 0.2
    ) -> Self:
        recv_q = asyncio.Queue[bytes]()
        buffer_free = asyncio.Event()
        transport = await _new_transport(host, port, recv_q, buffer_free)
        return cls(
            host,
            port,
            password.encode(encoding=_ENCODING),
            transport,
            recv_q,
            recv_timeout,
            buffer_free,
        )


def _duration_to_seconds(duration: str) -> int:
    if not duration:
        return 0
    if (unit := duration[-1].lower()) == "m":
        multiplier = 60
    elif unit == "h":
        multiplier = 3600
    elif unit == "d":
        multiplier = 86400
    elif unit == "w":
        multiplier = 604800
    else:
        multiplier = 1

    return int(duration if multiplier == 1 else duration[:-1]) * multiplier


def _wrap_message(message: str, width: int) -> list[str]:
    return [
        x.strip() for line in message.splitlines() for x in textwrap.wrap(line, width)
    ]


async def _new_transport(
    host: str, port: int, recv_q: asyncio.Queue[bytes], buffer_free: asyncio.Event
) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Protocol(recv_q, buffer_free), remote_addr=(host, port)
    )
    return cast(DatagramTransport, transport)  # type: ignore[redundant-cast]
