import asyncio
from asyncio import Future, Task
from types import TracebackType
from typing import Any, AsyncGenerator, Callable, Coroutine, Iterable, Type, TypeVar

from ._anyio import TaskGroup
from ._typing import AsyncioPoolMapWorkerType, AsyncioPoolWorkerType

T = TypeVar("T")
R = TypeVar("R")
CancelledError = asyncio.CancelledError


def _spawn_func_wrapper(
    future: Future[R], func: AsyncioPoolWorkerType[R], *args: Any, **kwargs: Any
) -> Callable[[], Coroutine[Any, Any, None]]:
    async def _wrapper() -> None:
        try:
            result = await func(*args, **kwargs)
            future.set_result(result)
        except BaseException as e:  # pylint: disable=broad-except
            future.set_exception(e)

    return _wrapper


def _make_name(*names: Any) -> str:
    return "-".join([x for x in names if bool(x)])


class AsyncioPool:
    """A pool of coroutine functions.

    `AsyncioPool` utilizes [anyio](https://anyio.readthedocs.io/en/stable/)'s
    [TaskGroup](https://anyio.readthedocs.io/en/stable/tasks.html) to manage the
    lifecycle of each function but adds the ability to limit how many run concurrently.

    For each function, a [Future](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future) is returned.
    This `Future` will hold the result of the function that was executed. Any exceptions raised inside the
    function are hidden from the `TaskGroup` and held within the `Future`.
    """

    _group: TaskGroup
    _size: int
    _semaphore: asyncio.Semaphore
    _pending: set[Future[Any]]

    __slots__ = (
        "_group",
        "_size",
        "_semaphore",
        "_pending",
    )

    def __init__(self, size: int = 100):
        """Initialize `AsyncioPool`.

        Args:
            size: Max number of coroutines which can run simultaneously.
        """
        self._group = TaskGroup()
        self._size = size
        self._semaphore = asyncio.Semaphore(size)
        self._pending = {*()}

    async def __aenter__(self) -> "AsyncioPool":
        await self._group.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        while self._pending:
            await asyncio.wait(self._pending, timeout=0.1)
        return await self._group.__aexit__(exc_type, exc_val, exc_tb)

    def __len__(self) -> int:
        """Count of all pending work still in the pool.

        Returns:
            Size of the pool.
        """
        return len(self._pending)

    @property
    def is_full(self) -> bool:
        """Return `True` if the pool has reached the maximum number of concurrent tasks.

        Returns:
            True/False
        """
        return len(self._pending) > self._size

    @property
    def is_empty(self) -> bool:
        """Return `True` if the pool has no tasks.

        Returns:
            True/False
        """
        return len(self._pending) == 0

    @property
    def _active(self) -> bool:
        return self._group._active  # pylint: disable=protected-access

    def _release_semaphore_callback(self, *_: Any) -> None:
        self._semaphore.release()

    def _remove_from_pending_callback(self, future: Future[Any]) -> None:
        self._pending.remove(future)

    def running_tasks(self) -> list[Task[Any]]:
        """Return all running tasks associated with the AsyncioPool instance.

        Returns:
            List of tasks
        """
        group_tasks = (
            self._group.cancel_scope._tasks  # pylint: disable=protected-access
        )
        return [
            x for x in group_tasks if x.get_name().startswith(f"{type(self).__name__}-")
        ]

    async def _spawn_to_pool(
        self,
        func: AsyncioPoolWorkerType[R],
        *args: Any,
        name: object = None,
        future: Future[R] | None = None,
        **kwargs: Any,
    ) -> Future[R]:
        """Schedules the callable, _func_, to be executed as `func(*args, **kwargs)`.

        This method returns a future which represents the
        execution of the callable once the future has completely.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            *args: Positional arguments for _func_
            name: Optional name for the `asyncio.Task`
            **kwargs: Keyword aarguments for _func_

        Returns:
            Future containing the results of _func_.
        """
        await self._semaphore.acquire()
        future = future if future else Future()
        wrapped_func = _spawn_func_wrapper(future, func, *args, **kwargs)
        self._group._spawn(wrapped_func, (), name)  # pylint: disable=protected-access
        future.add_done_callback(self._release_semaphore_callback)
        return future

    def spawn(
        self,
        func: AsyncioPoolWorkerType[R],
        *args: Any,
        name: str | None = None,
        **kwargs: Any,
    ) -> Future[R]:
        """Schedules the callable, _func_, to be executed as `func(*args, **kwargs)`.

        This method immediately returns a future which represents the execution of the callable.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            *args: Positional arguments for _func_
            name: Optional name for the `asyncio.Task`
            **kwargs: Keyword aarguments for _func_

        Returns:
            Future which will eventually contain the results of _func_.
        """
        if not self._active:
            raise RuntimeError(
                "This task pool is not active; no new tasks can be started."
            )

        # create future which will store the results once the task is done
        future: Future[R] = Future()
        self._pending.add(future)
        future.add_done_callback(self._remove_from_pending_callback)

        if name:
            name = _make_name(type(self).__name__, name)
        else:
            name = _make_name(type(self).__name__, str(func.__name__))

        # create task to wait/execute `func`
        asyncio.create_task(
            self._spawn_to_pool(func, *args, name=name, future=future, **kwargs),
            name=f"{type(self).__name__}-__spawn__",
        )

        return future

    def map(
        self,
        func: AsyncioPoolMapWorkerType[T, R],
        iterable: Iterable[T],
        name: str | None = None,
    ) -> set[Future[R]]:
        """Apply _func_ to every item of _iterable_.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            iterable: Iterable instance which produces values for _func_
            name: Optional name for the `asyncio.Task`

        Returns:
            Set of futures which will eventually contain the results of each _func_.
        """
        name = name if name else f"map({func.__name__})"

        return {
            self.spawn(func, item, name=f"{name}[{i}]")
            for i, item in enumerate(iterable)
        }

    async def itermap(
        self,
        func: AsyncioPoolMapWorkerType[T, R],
        iterable: Iterable[T],
        name: str | None = None,
        batch_duration: int | float = 0.1,
    ) -> AsyncGenerator[Future[R], None]:
        """Generate a future for _func_ for every item of _iterable_.

        Futures are yielded as they completed.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            iterable: Iterable instance which produces values for _func_
            name: Optional name for the `asyncio.Task`
            batch_duration: Duration to wait before yielding batches of completed futures.

        Returns:
            Async generator of futures.
        """
        name = name if name else f"itermap({func.__name__})"

        pending = self.map(func, iterable, name=name)
        while pending:
            done, pending = await asyncio.wait(pending, timeout=batch_duration)
            for future in done:
                yield future
