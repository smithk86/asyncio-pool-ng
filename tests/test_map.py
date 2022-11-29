import asyncio

import pytest

from asyncio_pool import AsyncioPool, AsyncioPoolWorker

from .utils import exception_worker, worker_ids, workers

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize("worker", workers, ids=worker_ids)
async def test_map(worker: AsyncioPoolWorker[int]) -> None:
    results: list[int] = []
    errors: list[BaseException] = []
    async with AsyncioPool(1000) as pool:
        futures = pool.map(worker, range(10000))
        [await future for future in futures]
        for future in futures:
            try:
                results.append(future.result())
            except BaseException as e:
                errors.append(e)

    assert len(results) == 10000
    assert len(errors) == 0


@pytest.mark.parametrize("worker", workers, ids=worker_ids)
async def test_map_exit_with_active_tasks(worker: AsyncioPoolWorker[int]) -> None:
    async with AsyncioPool(1000) as pool:
        futures = pool.map(worker, range(10000))

    done, pending = await asyncio.wait(futures)
    assert len(done) == 10000
    assert len(pending) == 0


async def test_map_with_exception() -> None:
    results: list[int] = []
    errors: list[BaseException] = []
    async with AsyncioPool(1000) as pool:
        futures = pool.map(exception_worker, range(10000))
        await asyncio.wait(futures)
        for future in futures:
            try:
                results.append(future.result())
            except BaseException as e:
                errors.append(e)

    assert len(results) == 0
    assert len(errors) == 10000
