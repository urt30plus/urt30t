"""
Urban Terror |30+| Game/Discord Bot
"""
from .core import Bot, BotCommandHandler, BotError, BotPlugin, __version__, bot_command
from .models import (
    Event,
    EventType,
    Game,
    GameState,
    GameType,
    Group,
    Player,
    PlayerState,
    Team,
)

__all__ = [
    "__version__",
    "Bot",
    "BotCommandHandler",
    "BotError",
    "BotPlugin",
    "Event",
    "EventType",
    "Game",
    "GameState",
    "GameType",
    "Group",
    "Player",
    "PlayerState",
    "Team",
    "bot_command",
]
