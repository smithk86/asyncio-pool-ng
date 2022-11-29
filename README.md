# asyncio-pool-ng

[![PyPI version](https://img.shields.io/pypi/v/asyncio-pool-ng)](https://pypi.org/project/asyncio-pool-ng/)
[![Python Versions](https://img.shields.io/pypi/pyversions/asyncio-pool-ng)](https://pypi.org/project/asyncio-pool-ng/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![](https://github.com/smithk86/asyncio-pool-ng/workflows/test-all/badge.svg)](https://github.com/smithk86/asyncio-pool-ng/actions?query=workflow%3Apytest)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## About

**AsyncioPoolNG** takes the ideas used in [asyncio-pool](https://github.com/gistart/asyncio-pool) and wraps them around a [TaskGroup](https://anyio.readthedocs.io/en/stable/tasks.html) from [anyio](https://anyio.readthedocs.io/en/stable/index.html).

`AsyncioPool` has three main functions `spawn`, `map`, and `itermap`.

1. `spawn`: Schedule an async function on the pool and get a future back which will eventually have either the result or the exception from the function.
2. `map`: Spawn an async function for each item in an iterable object, and return a set containing a future for each item.

- `asyncio.wait()` can be used to wait for the set of futures to complete.
- When the `AsyncioPool` closes, it will wait for all tasks to complete. All pending futures will be complete once it is closed.

3. `itermap`: Works similarly to `map` but returns an [Async Generator](https://docs.python.org/3/library/typing.html#typing.AsyncGenerator "Async Generator") which yields each future as it completes.

## Differences from asyncio-pool

1. `asyncio-pool-ng` implements [Python typing](https://typing.readthedocs.io/en/latest/) and passes validation checks with [mypy](http://mypy-lang.org/)'s strict mode. This helps IDEs and static type checkers know what type of result to expect when getting data from a completed future.
2. `asyncio-pool` uses callbacks to process data before returning it; `asyncio-pool-ng` only returns [Future](https://docs.python.org/3.10/library/asyncio-future.html#asyncio.Future) instances directly. The future will contain either a result or an exception which can then be handled as needed.
3. While `asyncio-pool` schedules [Coroutine](https://docs.python.org/3/library/typing.html#typing.Coroutine) instances directly, `asyncio-pool-ng` takes the callable and arguments, and creates the Coroutine instance at execution time.

## Example

```python title="example.py"
import asyncio
import logging
from random import random

from asyncio_pool import AsyncioPool


logging.basicConfig(level=logging.INFO)


async def worker(number: int) -> int:
    await asyncio.sleep(random() / 2)
    return number * 2


async def main() -> None:
    result: int = 0
    results: list[int] = []

    async with AsyncioPool(2) as pool:
        """spawn task and wait for the results"""
        result = await pool.spawn(worker, 5)
        assert result == 10
        logging.info(f"results for pool.spawn(worker, 5): {result}")

        """spawn task and get results later"""
        future: asyncio.Future[int] = pool.spawn(worker, 5)

        # do other stuff

        result = await future
        assert result == 10

        """map an async function to a set of values"""
        futures: set[asyncio.Future[int]] = pool.map(worker, range(10))
        await asyncio.wait(futures)
        results = [x.result() for x in futures]
        logging.info(f"results for pool.map(worker, range(10)): {results}")
        results.sort()
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

        """iterate futures as they complete"""
        logging.info("results for pool.itermap(worker, range(10)):")
        results = []
        async for future in pool.itermap(worker, range(10)):
            results.append(future.result())
            logging.info(f"> {future.result()}")

        results.sort()
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]


asyncio.run(main())
```
