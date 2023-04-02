import asyncio
import logging
from types import TracebackType
from typing import Self

import asyncio_dgram
from asyncio_dgram.aio import DatagramClient

from . import settings

logger = logging.getLogger(__name__)


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

            logger.warning("RCON %s: no data on try %s", cmd, i)
            await asyncio.sleep(self.read_timeout * i + 1)

        raise RconNoDataError(cmd)

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
