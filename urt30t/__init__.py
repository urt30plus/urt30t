"""
Urban Terror |30+| Game/Discord Bot
"""
from urt30arcon import GameType, Team

from .core import (
    bot_command,
    bot_subscribe,
)
from .models import (
    Bot,
    BotCommand,
    BotError,
    BotPlugin,
    CommandHandler,
    FlagAction,
    Game,
    Group,
    MessageType,
    Player,
)
from .version import __version__

__all__ = [
    "__version__",
    "Bot",
    "BotCommand",
    "BotError",
    "BotPlugin",
    "CommandHandler",
    "FlagAction",
    "Game",
    "GameType",
    "Group",
    "MessageType",
    "Player",
    "Team",
    "bot_command",
    "bot_subscribe",
]
