from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


AsyncioPoolWorkerType = Callable[..., Coroutine[Any, Any, R]]
AsyncioPoolMapWorkerType = Callable[[T], Coroutine[Any, Any, R]]
