import asyncio
import functools
import os
import sys

import msgpack
import pytest
from redislite import Redis

from arq.connections import ArqRedis, ArqRedisCluster, RedisSettings, create_pool
from arq.worker import Worker


@pytest.fixture(name='loop')
def _fix_loop(event_loop):
    return event_loop


@pytest.fixture
async def arq_redis(loop):
    if os.getenv('CLUSTER_MODE') == 'true':
        pytest.skip('Needs standalone instance to run')
    redis_ = ArqRedis(
        host='localhost',
        port=6379,
        encoding='utf-8',
    )

    await redis_.flushall()

    yield redis_

    await redis_.close(close_connection_pool=True)


@pytest.fixture
async def unix_socket_path(loop, tmp_path):
    rdb = Redis(str(tmp_path / 'redis_test.db'))
    yield rdb.socket_file
    rdb.close()


@pytest.fixture
async def arq_redis_msgpack(loop):
    if os.getenv('CLUSTER_MODE') == 'true':
        pytest.skip('Needs standalone instance to run')
    redis_ = ArqRedis(
        host='localhost',
        port=6379,
        encoding='utf-8',
        job_serializer=msgpack.packb,
        job_deserializer=functools.partial(msgpack.unpackb, raw=False),
    )
    await redis_.flushall()
    yield redis_
    await redis_.close(close_connection_pool=True)


# @pytest.fixture(autouse=False)
# async def arq_redis_cluster(loop):
#     if os.getenv('CLUSTER_MODE') == 'false':
#         pytest.skip('Needs cluster instance to run')
#     settings = RedisSettings(host='localhost', port=6379, conn_timeout=5, cluster_mode=True)
#     redis_ = await create_pool(settings)
#     await redis_.flushall()

#     yield redis_
#     await redis_.aclose()


@pytest.fixture
async def arq_redis_cluster(loop):
    if os.getenv('CLUSTER_MODE') == 'false':
        pytest.skip('Needs standalone instance to run')
    redis_ = ArqRedisCluster(
        host='localhost',
        port=6379,
        encoding='utf-8',
    )

    await redis_.flushall()

    yield redis_

    await redis_.close()


@pytest.fixture
async def worker(arq_redis):
    if os.getenv('CLUSTER_MODE') == 'true':
        pytest.skip('Needs standalone instance to run')
    worker_: Worker = None

    def create(functions=[], burst=True, poll_delay=0, max_jobs=10, arq_redis=arq_redis, **kwargs):
        nonlocal worker_
        worker_ = Worker(
            functions=functions, redis_pool=arq_redis, burst=burst, poll_delay=poll_delay, max_jobs=max_jobs, **kwargs
        )
        return worker_

    yield create

    if worker_:
        await worker_.close()


@pytest.fixture
async def cluster_worker(arq_redis_cluster):
    if os.getenv('CLUSTER_MODE') == 'false':
        pytest.skip('Needs cluster instance to run')
    worker_: Worker = None

    def create(functions=[], burst=True, poll_delay=0, max_jobs=10, arq_redis_cluster=arq_redis_cluster, **kwargs):
        nonlocal worker_
        worker_ = Worker(
            functions=functions,
            redis_pool=arq_redis_cluster,
            burst=burst,
            poll_delay=poll_delay,
            max_jobs=max_jobs,
            redis_settings=RedisSettings(host='localhost', port=6379, conn_timeout=5, cluster_mode=True),
            **kwargs,
        )
        return worker_

    yield create

    if worker_:
        await worker_.close()


@pytest.fixture(name='create_pool')
async def fix_create_pool(loop):
    pools = []

    async def create_pool_(settings, *args, **kwargs):
        pool = await create_pool(settings, *args, **kwargs)
        pools.append(pool)
        return pool

    yield create_pool_

    await asyncio.gather(*[p.close(close_connection_pool=True) for p in pools])


@pytest.fixture(name='cancel_remaining_task')
def fix_cancel_remaining_task(loop):
    async def cancel_remaining_task():
        tasks = asyncio.all_tasks(loop)
        cancelled = []
        for task in tasks:
            # in repr works in 3.7 where get_coro() is not available
            if 'cancel_remaining_task()' not in repr(task):
                cancelled.append(task)
                task.cancel()
        if cancelled:
            print(f'Cancelled {len(cancelled)} ongoing tasks', file=sys.stderr)
            await asyncio.gather(*cancelled, return_exceptions=True)

    yield

    loop.run_until_complete(cancel_remaining_task())


class SetEnv:
    def __init__(self):
        self.envars = set()

    def set(self, name, value):
        self.envars.add(name)
        os.environ[name] = value

    def clear(self):
        for n in self.envars:
            os.environ.pop(n)


@pytest.fixture
def env():
    setenv = SetEnv()

    yield setenv

    setenv.clear()
