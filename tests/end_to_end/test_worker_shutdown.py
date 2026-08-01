import asyncio
import signal

import pytest

from apps.worker.main import WorkerDaemon


@pytest.mark.asyncio
async def test_worker_graceful_shutdown():
    worker = WorkerDaemon()
    worker_task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)

    assert worker.running is True
    worker.handle_signal(signal.SIGTERM, None)
    await worker_task
    assert worker.running is False
