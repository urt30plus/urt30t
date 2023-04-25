from typing import Protocol

import discord


class EmbedUpdater(Protocol):
    channel_name: str
    embed_title: str

    async def fetch_embed_message(self) -> discord.Message | None:
        ...

    async def new_message(self, embed: discord.Embed) -> discord.Message:
        ...
