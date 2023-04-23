import logging
from typing import Any

import discord

logger = logging.getLogger(__name__)


class DiscordClientError(Exception):
    pass


class ServerNotFoundError(DiscordClientError):
    pass


class ChannelNotFoundError(DiscordClientError):
    pass


class InvalidChannelTypeError(DiscordClientError):
    def __init__(self, channel: discord.abc.GuildChannel) -> None:
        super().__init__(channel.name, channel.type)


class GuildNotFoundError(DiscordClientError):
    pass


class DiscordClient(discord.Client):
    def __init__(
        self,
        bot_user: str,
        server_name: str,
        **kwargs: Any,
    ) -> None:
        if "intents" not in kwargs:
            kwargs["intents"] = discord.Intents.all()
        super().__init__(**kwargs)
        self.bot_user = bot_user
        self.server_name = server_name
        self._guild: discord.Guild | None = None

    async def login(self, token: str) -> None:
        await super().login(token)
        async for guild in super().fetch_guilds():
            if guild.name == self.server_name:
                self._guild = guild
                break
        else:
            raise ServerNotFoundError(self.server_name)

    async def _channel_by_name(self, name: str) -> discord.TextChannel:
        logger.info("Looking for channel named [%s]", name)
        if self._guild is None:
            raise GuildNotFoundError(name)
        channels = await self._guild.fetch_channels()
        for ch in channels:
            if ch.name == name:
                logger.info("Found channel: %s [%s]", ch.name, ch.id)
                if isinstance(ch, discord.TextChannel):
                    return ch
                raise InvalidChannelTypeError(ch)

        raise ChannelNotFoundError(name)

    async def _last_messages(
        self,
        channel: discord.TextChannel,
        limit: int = 1,
    ) -> list[discord.Message]:
        messages = []
        logger.info(
            "Fetching last %s messages if posted by %r in channel %s",
            limit,
            self.bot_user,
            channel.name,
        )
        async for msg in channel.history(limit=limit):
            author = msg.author
            author_user = f"{author.name}#{author.discriminator}"
            if author.bot and author_user == self.bot_user:
                messages.append(msg)
        logger.info("Found [%s] messages", len(messages))
        return messages

    async def _find_message_by_embed_title(
        self,
        channel: discord.TextChannel,
        embed_title: str,
        limit: int = 5,
    ) -> discord.Message | None:
        messages = await self._last_messages(channel, limit=limit)
        logger.info("Looking for message with the %r embed title", embed_title)
        for msg in messages:
            for embed in msg.embeds:
                if embed.title == embed_title:
                    return msg
        return None

    async def fetch_embed_message(
        self,
        channel_name: str,
        embed_title: str,
        limit: int = 5,
    ) -> tuple[discord.TextChannel, discord.Message | None]:
        channel = await self._channel_by_name(channel_name)
        message = await self._find_message_by_embed_title(
            channel=channel,
            embed_title=embed_title,
            limit=limit,
        )
        return channel, message

    def __str__(self) -> str:
        return f"Bot30Client(bot_user={self.bot_user!r}, server={self.server_name!r})"
