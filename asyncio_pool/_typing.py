from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")
R = TypeVar("R")


AsyncioPoolWorkerType = Callable[..., Coroutine[Any, Any, R]]
AsyncioPoolMapWorkerType = Callable[[T], Coroutine[Any, Any, R]]
