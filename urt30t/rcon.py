import asyncio
import contextlib
import logging
import re
from collections.abc import Iterator
from types import TracebackType
from typing import Self

import asyncio_dgram
from asyncio_dgram.aio import DatagramClient

from . import settings
from .models import Cvar, Game

logger = logging.getLogger(__name__)

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


class RconError(Exception):
    pass


class RconClient:
    CMD_PREFIX = b"\xff" * 4
    REPLY_PREFIX = CMD_PREFIX + b"print\n"
    ENCODING = "latin-1"

    def __init__(  # noqa: PLR0913
        self,
        host: str,
        port: int,
        rcon_pass: str,
        connect_timeout: float = settings.rcon.connect_timeout,
        read_timeout: float = settings.rcon.read_timeout,
    ) -> None:
        self.host = host
        self.port = port
        self.rcon_pass = rcon_pass
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.stream: DatagramClient | None = None
        self.lock = asyncio.Lock()
        self.tasks = set()

    @contextlib.asynccontextmanager
    async def connect(self) -> Iterator[DatagramClient]:
        if self.stream is None:
            logger.info("connecting stream to %s:%s", self.host, self.port)
            self.stream = await asyncio_dgram.connect((self.host, self.port))
        async with self.lock:
            yield self.stream

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        self.close()

    async def send(self, cmd: str, retries: int = 0) -> str:
        max_range = 2 if retries <= 0 else retries + 2
        async with self.connect() as stream:
            for i in range(1, max_range):
                data, reply_received = await self._send(stream, cmd)
                if data:
                    return data
                if reply_received:
                    return ""

                logger.warning("command %s: no reply received on try %s", cmd, i)
                await asyncio.sleep(self.read_timeout * i + 1)

            return data

    async def send_many(self, cmds: list[str]) -> None:
        task = asyncio.create_task(self._send_many(cmds))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def cvar(self, name: str) -> Cvar | None:
        data = await self.send(name)
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

    async def game_info(self, *, retries: int = 3) -> Game:
        cmd = "players"
        data = await self.send(cmd, retries=retries)
        logger.debug("command %s: payload:\n%s", cmd, data)
        return Game.from_string(data)

    async def _send(self, stream: DatagramClient, cmd: str) -> tuple[str, bool]:
        rcon_cmd = self._create_rcon_cmd(cmd)
        await stream.send(rcon_cmd)
        data, reply_received = await self._receive(stream)
        return data.decode(self.ENCODING), reply_received

    async def _send_many(self, cmds: list[str]) -> None:
        async with self.connect() as stream:
            for cmd in cmds:
                await self._send(stream, cmd)

    async def _receive(self, stream: DatagramClient) -> tuple[bytearray, bool]:
        result = bytearray()
        reply_received = False
        while True:
            try:
                data, _ = await asyncio.wait_for(
                    stream.recv(),
                    timeout=self.read_timeout,
                )
                result += data.replace(self.REPLY_PREFIX, b"", 1)
                reply_received = True
            except asyncio.TimeoutError:
                break

        return result, reply_received

    def _create_rcon_cmd(self, cmd: str) -> bytes:
        return self.CMD_PREFIX + f'rcon "{self.rcon_pass}" {cmd}\n'.encode(
            self.ENCODING
        )
