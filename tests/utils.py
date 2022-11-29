import asyncio
from contextlib import contextmanager
from time import perf_counter
from typing import Callable, Generator

from asyncio_pool import AsyncioPoolWorker


@contextmanager
def timer() -> Generator[Callable[[], float], None, None]:
    t1 = t2 = perf_counter()
    yield lambda: t2 - t1
    t2 = perf_counter()


async def worker_1(n: int) -> int:
    await asyncio.sleep(0)
    return n


async def worker_2(n: int) -> int:
    await asyncio.sleep(0.001)
    return n


workers: list[AsyncioPoolWorker[int]] = [worker_1, worker_2]
worker_ids: list[str] = ["worker_1", "worker_2"]


async def worker_long(n: int) -> int:
    await asyncio.sleep(1)
    return n


async def worker_args(
    n: int, s: str, kw1: int = 123, kw2: str | None = None
) -> tuple[int, str, int, str | None]:
    await asyncio.sleep(0)
    return (n, s, kw1, kw2)


async def exception_worker(_: int) -> int:
    raise RuntimeError("task failed")
