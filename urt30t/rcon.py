import asyncio
import logging
import re
from asyncio.transports import DatagramTransport
from typing import Any, cast

from .models import Cvar, Game

logger = logging.getLogger(__name__)

CMD_PREFIX = b"\xff" * 4
REPLY_PREFIX = CMD_PREFIX + b"print\n"
ENCODING = "latin-1"

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
            logger.exception(exc)
        if size := self._recv_q.qsize():
            logger.warning("Receive queue has pending items: %s", size)
        if self._transport:
            self._transport.close()

    def datagram_received(self, data: bytes, _: tuple[str | Any, int]) -> None:
        self._recv_q.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        logger.exception(exc)

    def pause_writing(self) -> None:
        self._buffer_free.clear()

    def resume_writing(self) -> None:
        self._buffer_free.set()


class RconClient:
    def __init__(
        self,
        password: bytes,
        transport: DatagramTransport,
        recv_q: asyncio.Queue[bytes],
        recv_timeout: float,
        buffer_free: asyncio.Event,
    ) -> None:
        self._password = password
        self._transport = transport
        self._recv_q = recv_q
        self._recv_timeout = recv_timeout
        self._buffer_free = buffer_free

    async def bigtext(self, message: str) -> None:
        await self._send(f'bigtext "{message}"')

    async def broadcast(self, message: str) -> None:
        await self._send(f'"{message}"')

    def close(self) -> None:
        self._transport.close()

    async def cvar(self, name: str) -> Cvar | None:
        data = await self._send(name.encode(encoding=ENCODING))
        for pat in _CVAR_PATTERNS:
            if m := pat.match(data):
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

    async def cycle_map(self) -> None:
        await self._send(b"cyclemap")

    async def map_restart(self) -> None:
        await self._send(b"map_restart")

    async def message(self, message: str) -> None:
        await self._send(f'say "{message}"')

    async def players(self) -> Game:
        data = await self._send(b"players", retry=True)
        return Game.from_string(data)

    async def private_message(self, slot: str, message: str) -> None:
        await self._send(f'tell {slot} "{message}"')

    async def reload(self) -> None:
        await self._send(b"reload")

    async def shuffle_teams(self) -> None:
        await self._send(b"shuffleteams")

    async def swap_teams(self) -> None:
        await self._send(b"swapteams")

    async def _send(self, cmd: str | bytes, *, retry: bool = False) -> str:
        if isinstance(cmd, str):
            cmd = cmd.encode(encoding=ENCODING)
        cmd = b'%srcon "%s" %s\n' % (CMD_PREFIX, self._password, cmd)
        self._transport.sendto(cmd)
        await self._buffer_free.wait()
        try:
            data = await asyncio.wait_for(
                self._recv_q.get(), timeout=self._recv_timeout
            )
            if data.startswith(REPLY_PREFIX):
                return data.replace(REPLY_PREFIX, b"", 1).decode(encoding=ENCODING)
            logger.error("invalid reply for command: %r - %r", cmd, data)
        except asyncio.TimeoutError:
            pass

        if retry:
            return await self._send(cmd, retry=False)

        return ""

    def __repr__(self) -> str:
        return (
            f"RconClient(host={self._transport.get_extra_info('peername')}, "
            f"recv_timeout={self._recv_timeout})"
        )


async def create_client(
    host: str, port: int, password: str, recv_timeout: float = 0.2
) -> RconClient:
    loop = asyncio.get_running_loop()

    recv_q = asyncio.Queue[bytes]()
    buffer_free = asyncio.Event()

    transport: asyncio.DatagramTransport
    transport, proto = await loop.create_datagram_endpoint(
        lambda: _Protocol(recv_q, buffer_free), remote_addr=(host, port)
    )

    return RconClient(
        password.encode(encoding=ENCODING), transport, recv_q, recv_timeout, buffer_free
    )
