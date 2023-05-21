import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
from time import perf_counter

from asyncio_pool import AsyncioPoolWorkerType


@contextmanager
def timer() -> Generator[Callable[[], float], None, None]:
    t1 = t2 = perf_counter()
    yield lambda: t2 - t1
    t2 = perf_counter()


async def worker_return_int1(n: int) -> int:
    await asyncio.sleep(0)
    return n


async def worker_return_int2(n: int) -> int:
    await asyncio.sleep(0.001)
    return n


async def worker_return_str(n: int) -> str:
    await asyncio.sleep(0)
    return str(n)


workers: list[AsyncioPoolWorkerType[int]] = [worker_return_int1, worker_return_int2]
worker_ids: list[str] = ["worker1", "worker2"]


async def worker_long(n: int) -> int:
    await asyncio.sleep(1)
    return n


async def worker_args(n: int, s: str, kw1: int = 123, kw2: str | None = None) -> tuple[str | None, int, str, int]:
    await asyncio.sleep(0)
    return (kw2, kw1, s, n)


async def exception_worker(_: int) -> int:
    raise RuntimeError("task failed")
