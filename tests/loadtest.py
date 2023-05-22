# This script was copied and modified from https://github.com/gistart/asyncio-pool/blob/cd79fe782f97c6a268f61307a80397744d6c3f4b/tests/loadtest.py

import argparse
import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any

from asyncio_pool import AsyncioPool

LoadTestMethod = Callable[[int, int, float], Coroutine[Any, Any, Any]]


async def loadtest_spawn(tasks: int, pool_size: int, duration: float) -> list[asyncio.Future[None]]:
    futures: list[asyncio.Future[None]] = []
    async with AsyncioPool(pool_size) as pool:
        for _ in range(tasks):
            fut = pool.spawn(asyncio.sleep, duration)
            futures.append(fut)

    return futures


async def loadtest_map(tasks: int, pool_size: int, duration: float) -> set[asyncio.Future[None]]:
    async def wrk(_: int) -> None:
        await asyncio.sleep(duration)

    async with AsyncioPool(pool_size) as pool:
        return pool.map(wrk, range(tasks))


async def loadtest_itermap(tasks: int, pool_size: int, duration: float) -> list[asyncio.Future[None]]:
    async def wrk(_: int) -> None:
        await asyncio.sleep(duration)

    futures: list[asyncio.Future[None]] = []
    async with AsyncioPool(pool_size) as pool:
        async for fut in pool.itermap(wrk, range(tasks), batch_duration=5.0):
            futures.append(fut)

    return futures


def print_stats(args: Any, exec_time: float) -> None:
    ideal = args.task_duration * (args.tasks / args.pool_size)
    overhead = exec_time - ideal
    per_task = overhead / args.tasks
    overhead_perc = ((exec_time / ideal) - 1) * 100

    print(f"{ideal:15.5f}s -- ideal result")
    print(f"{exec_time:15.5f}s -- total executing time")
    print(f"{overhead:15.5f}s -- total overhead")
    print(f"{per_task:15.5f}s -- overhead per task")
    print(f"{overhead_perc:13.3f}%   -- overhead total percent")


if __name__ == "__main__":
    methods: dict[str, LoadTestMethod] = {
        "spawn": loadtest_spawn,
        "map": loadtest_map,
        "itermap": loadtest_itermap,
    }

    p = argparse.ArgumentParser()
    p.add_argument("method", choices=methods.keys())
    p.add_argument("--tasks", "-t", type=int, default=10**5)
    p.add_argument("--task-duration", "-d", type=float, default=0.2)
    p.add_argument("--pool-size", "-p", type=int, default=10**3)
    args = p.parse_args()

    print(
        ">>> Running %d tasks in pool of size=%s, each task takes %.3f sec."
        % (args.tasks, args.pool_size, args.task_duration)
    )
    print(">>> This will run more than %.5f seconds" % (args.task_duration * (args.tasks / args.pool_size)))

    ts_start = time.perf_counter()

    if args.method in methods:
        m = methods[args.method](args.tasks, args.pool_size, args.task_duration)
        asyncio.get_event_loop().run_until_complete(m)
        exec_time = time.perf_counter() - ts_start
        print_stats(args, exec_time)
    else:
        raise KeyError(f"method not found: {args.method}")
