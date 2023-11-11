"""
Urban Terror |30+| Game/Discord Bot
"""

# this import should come first in order to init logging
# and to fail fast in the event of a mis-configuration
from .settings import __version__  # noqa: I001

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
