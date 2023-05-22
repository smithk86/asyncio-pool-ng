from asyncio import Future, Queue, Semaphore, Task, TaskGroup, create_task, sleep, wait
from asyncio.queues import QueueEmpty
from collections.abc import AsyncGenerator, Coroutine, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import Context
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from ._typing import AsyncioPoolMapWorkerType, AsyncioPoolWorkerType

__all__ = ["AsyncioPool"]


T = TypeVar("T")
R = TypeVar("R")


@dataclass
class PendingTask(Generic[R]):
    func: AsyncioPoolWorkerType[R]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    name: str | None = None
    context: Context | None = None

    def wrapped(self, future: Future[R]) -> Coroutine[Any, Any, None]:
        async def wrapper() -> None:
            try:
                result = await self.func(*self.args, **self.kwargs)
                future.set_result(result)
            except Exception as e:  # noqa: BLE001
                future.set_exception(e)

        return wrapper()


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
    _queue: Queue[tuple[Future[Any], PendingTask[Any]]]
    _pending: set[Future[Any]]
    _semaphore: Semaphore
    _exit_stack: AsyncExitStack

    __slots__ = (
        "_group",
        "_size",
        "_semaphore",
        "_queue",
        "_pending",
        "_exit_stack",
    )

    def __init__(self, size: int = 100) -> None:
        """Initialize ``AsyncioPool``.

        Args:
            size: Max number of coroutines which can run simultaneously.
        """
        self._group = TaskGroup()
        self._size = size
        self._semaphore = Semaphore(size)
        self._queue = Queue()
        self._pending = {*()}
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "AsyncioPool":
        await self._exit_stack.enter_async_context(self._consumer())
        await self._exit_stack.enter_async_context(self._group)
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Wait for all active tasks to complete."""
        await self.join()
        await self._exit_stack.aclose()

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
        return self._semaphore.locked()

    @property
    def is_empty(self) -> bool:
        """Return `True` if the pool has no tasks.

        Returns:
            True/False
        """
        return len(self._pending) == 0

    @property
    def _exiting(self) -> bool:
        return cast(bool, self._group._exiting)  # type: ignore[attr-defined]

    @property
    def _tasks(self) -> set[Task[T]]:
        return cast(set[Task[T]], self._group._tasks)  # type: ignore[attr-defined]

    @asynccontextmanager
    async def _consumer(self) -> AsyncGenerator[Task[None], None]:
        def release(_: Task[T]) -> None:
            self._semaphore.release()

        async def loop() -> None:
            while not self._exiting or len(self._pending) > 0:
                try:
                    future, pending_task = self._queue.get_nowait()
                except QueueEmpty:
                    await sleep(0)
                    continue

                await self._semaphore.acquire()
                coro = pending_task.wrapped(future)
                task = self._group.create_task(coro, name=pending_task.name, context=pending_task.context)
                task.add_done_callback(release)

        task = create_task(loop(), name="AsyncioPool-consumer")
        yield task
        await task

    async def join(self) -> None:
        """Wait for all active tasks to complete."""
        while self._pending:
            await sleep(0)

    def spawn(
        self,
        func: AsyncioPoolWorkerType[R],
        *args: Any,
        name: str | None = None,
        context: Context | None = None,
        **kwargs: Any,
    ) -> Future[R]:
        """Schedules the callable, _func_, to be executed as `func(*args, **kwargs)`.

        This method immediately returns a future which represents the execution of the callable.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            *args: Positional arguments for _func_
            name: Optional name for the `asyncio.Task`
            context: Optional context argument allows specifying a custom
                [contextvars.Context](https://docs.python.org/3/library/contextvars.html#contextvars.Context)
                for the coro to run in. The current context copy is created when no context is provided.
            **kwargs: Keyword aarguments for _func_

        Returns:
            Future which will eventually contain the results of _func_.
        """
        if self._exiting:
            raise RuntimeError("This task pool is not active; no new tasks can be started.")

        # create future which will store the results once the task is done
        future: Future[R] = Future()
        self._pending.add(future)
        future.add_done_callback(self._pending.discard)

        name = _make_name(type(self).__name__, name) if name else _make_name(type(self).__name__, str(func.__name__))

        # create task to wait/execute `func`
        self._queue.put_nowait(
            (
                future,
                PendingTask(
                    func=func,
                    name=name,
                    context=context,
                    args=args,
                    kwargs=kwargs,
                ),
            )
        )

        return future

    def map(
        self,
        func: AsyncioPoolMapWorkerType[T, R],
        iterable: Iterable[T],
        name: str | None = None,
        context: Context | None = None,
    ) -> set[Future[R]]:
        """Apply _func_ to every item of _iterable_.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            iterable: Iterable instance which produces values for _func_
            name: Optional name for the `asyncio.Task`
            context: Optional context argument allows specifying a custom
                [contextvars.Context](https://docs.python.org/3/library/contextvars.html#contextvars.Context)
                for the coro to run in. The current context copy is created when no context is provided.

        Returns:
            Set of futures which will eventually contain the results of each _func_.
        """
        name = name if name else f"map({func.__name__})"

        return {self.spawn(func, item, name=f"{name}[{i}]", context=context) for i, item in enumerate(iterable)}

    async def itermap(
        self,
        func: AsyncioPoolMapWorkerType[T, R],
        iterable: Iterable[T],
        name: str | None = None,
        context: Context | None = None,
        batch_duration: int | float = 0.1,
    ) -> AsyncGenerator[Future[R], None]:
        """Generate a future for _func_ for every item of _iterable_.

        Futures are yielded as they completed.

        Args:
            func: Function created with [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def)
            iterable: Iterable instance which produces values for _func_
            name: Optional name for the `asyncio.Task`
            context: Optional context argument allows specifying a custom
                [contextvars.Context](https://docs.python.org/3/library/contextvars.html#contextvars.Context)
                for the coro to run in. The current context copy is created when no context is provided.
            batch_duration: Duration to wait before yielding batches of completed futures.

        Returns:
            Async generator of futures.
        """
        name = name if name else f"itermap({func.__name__})"

        pending = self.map(func, iterable, name=name, context=context)
        while pending:
            done, pending = await wait(pending, timeout=batch_duration)
            for future in done:
                yield future
