from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


AsyncioPoolWorker = Callable[..., Coroutine[Any, Any, T]]
