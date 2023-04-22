import asyncio
from collections.abc import Coroutine
from typing import Any

_tasks = set()


def background(coro: Coroutine[Any, None, Any]) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
