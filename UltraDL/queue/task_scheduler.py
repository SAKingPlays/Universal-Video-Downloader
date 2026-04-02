"""
Thread-pool scheduler draining ``DownloadQueue``.

Workers block on ``queue.get_next``; each task runs inside ``DownloadManager``'s
executor closure. Cooperative pause is modeled by ``task.pause_event`` — future
versions may thread this into ``SegmentDownloader`` directly.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .download_queue import DownloadQueue, DownloadTask, TaskState

log = logging.getLogger("ultradl.scheduler")


class TaskScheduler:
    def __init__(
        self,
        queue: DownloadQueue,
        *,
        worker_count: int = 2,
        executor_fn: Optional[Callable[[DownloadTask], object]] = None,
    ) -> None:
        self.queue = queue
        self.worker_count = max(1, worker_count)
        self._executor_fn = executor_fn or self._default_run
        self._pool: Optional[ThreadPoolExecutor] = None
        self._shutdown = threading.Event()

    def start(self) -> None:
        if self._pool:
            return
        self._pool = ThreadPoolExecutor(max_workers=self.worker_count, thread_name_prefix="ultradl")
        for i in range(self.worker_count):
            self._pool.submit(self._worker_loop, i)

    def shutdown(self, *, wait: bool = True) -> None:
        self._shutdown.set()
        if self._pool:
            self._pool.shutdown(wait=wait, cancel_futures=True)
            self._pool = None

    def _worker_loop(self, idx: int) -> None:
        log.debug("scheduler worker %s online", idx)
        while not self._shutdown.is_set():
            task = self.queue.get_next(timeout=0.25)
            if not task:
                continue
            if task.cancel_event.is_set():
                self.queue.complete(task.id, error="cancelled")
                continue
            try:
                self._executor_fn(task)
                self.queue.complete(task.id)
            except Exception as exc:  # noqa: BLE001
                log.exception("Task failed: %s", task.url)
                self.queue.complete(task.id, error=str(exc))

    def _default_run(self, task: DownloadTask) -> None:
        log.info("Would run task %s (%s)", task.id, task.url)
        time.sleep(0.01)
