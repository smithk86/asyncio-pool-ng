import pytest

from asyncio_pool import AsyncioPool, AsyncioPoolMapWorkerType

from .utils import arange, exception_worker, worker_ids, worker_long, workers

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize("worker", workers, ids=worker_ids)
async def test_itermap_sync(worker: AsyncioPoolMapWorkerType[int, int]) -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for future in pool.itermap(worker, range(10000), batch_duration=0.1):
            try:
                results.append(future.result())
            except BaseException as e:
                errors.append(e)

        assert len(results) == 10000
        assert len(errors) == 0


async def test_itermap_sync_with_exception() -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for future in pool.itermap(exception_worker, range(10000), batch_duration=0.1):
            try:
                results.append(future.result())
            except Exception as e:
                errors.append(e)

        assert len(results) == 0
        assert len(errors) == 10000


@pytest.mark.parametrize("worker", workers, ids=worker_ids)
async def test_itermap_async(worker: AsyncioPoolMapWorkerType[int, int]) -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for future in pool.itermap(worker, arange(10000), batch_duration=0.1):
            try:
                results.append(future.result())
            except BaseException as e:
                errors.append(e)

        assert len(results) == 10000
        assert len(errors) == 0


async def test_itermap_async_long() -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for future in pool.itermap(worker_long, arange(20), batch_duration=0.1):
            try:
                results.append(future.result())
            except BaseException as e:
                errors.append(e)

        assert len(results) == 20
        assert len(errors) == 0


async def test_itermap_async_with_exception() -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for future in pool.itermap(exception_worker, arange(10000), batch_duration=0.1):
            try:
                results.append(future.result())
            except Exception as e:
                errors.append(e)

        assert len(results) == 0
        assert len(errors) == 10000
