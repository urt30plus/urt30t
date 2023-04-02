import asyncio
import logging
import re
from types import TracebackType
from typing import Self

import asyncio_dgram
from asyncio_dgram.aio import DatagramClient

from . import game, settings

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


class RconNoDataError(RconError):
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

    async def connect(self) -> DatagramClient:
        if self.stream is None:
            logger.info("connecting stream to %s:%s", self.host, self.port)
            self.stream = await asyncio_dgram.connect((self.host, self.port))
        return self.stream

    async def close(self) -> None:
        if self.stream is not None:
            self.stream.close()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.close()

    async def send(self, cmd: str, retries: int = 2) -> str:
        stream = await self.connect()
        rcon_cmd = self._create_rcon_cmd(cmd)
        for i in range(1, retries + 1):
            await stream.send(rcon_cmd)
            data = await self._receive()
            if data:
                return data.decode(self.ENCODING)

            logger.warning("Rcon %s: no data on try %s", cmd, i)
            await asyncio.sleep(self.read_timeout * i + 1)

        raise RconNoDataError(cmd)

    async def cvar(self, name: str) -> game.Cvar | None:
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

        return game.Cvar(name=name, value=m["value"], default=default)

    def _create_rcon_cmd(self, cmd: str) -> bytes:
        return self.CMD_PREFIX + f'rcon "{self.rcon_pass}" {cmd}\n'.encode(
            self.ENCODING
        )

    async def _receive(self) -> bytearray:
        stream = await self.connect()
        result = bytearray()
        while True:
            try:
                data, _ = await asyncio.wait_for(
                    stream.recv(),
                    timeout=self.read_timeout,
                )
                result += data.replace(self.REPLY_PREFIX, b"", 1)
            except asyncio.TimeoutError:
                break
        return result


client = RconClient(
    host=settings.rcon.host,
    port=settings.rcon.port,
    rcon_pass=settings.rcon.password,
    connect_timeout=settings.rcon.connect_timeout,
    read_timeout=settings.rcon.read_timeout,
)
