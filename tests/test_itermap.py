import pytest

from asyncio_pool import AsyncioPool, AsyncioPoolMapWorkerType

from .utils import exception_worker, worker_ids, workers

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize("worker", workers, ids=worker_ids)
async def test_itermap(worker: AsyncioPoolMapWorkerType[int, int]) -> None:
    async with AsyncioPool(1000) as pool:
        results: list[int] = []
        errors: list[BaseException] = []
        async for task in pool.itermap(worker, range(10000), batch_duration=0.1):
            try:
                results.append(task.result())
            except BaseException as e:
                errors.append(e)

        assert len(results) == 10000
        assert len(errors) == 0


async def test_itermap_with_exception() -> None:
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
