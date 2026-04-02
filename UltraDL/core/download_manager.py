"""
Multi-job façade coordinating configuration, HTTP client lifetime, and queue.

``DownloadManager`` owns shared resources (``HTTPClient``, extractor registry)
so a CLI session or GUI window can enqueue many URLs without reconnect storms.

Playlist/channel expansion reuses extractor ``discover_related`` hooks and
generic link crawling with a configurable depth budget.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Set

from ..extractors import ExtractorContext, get_default_registry
from ..queue.download_queue import DownloadQueue, DownloadTask, TaskPriority
from ..queue.task_scheduler import TaskScheduler
from ..utils.config_loader import AppConfig
from ..utils.logger import get_logger
from ..utils.network_utils import HTTPClient
from .downloader import DownloadResult, DownloadSession, VideoDownloader

log = get_logger("manager")

ProgressCallback = Callable[[str, float, float, float], None]  # task_id, pct, speed, eta


class DownloadManager:
    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig()
        self.http = HTTPClient(self.config.user_agent, timeout=self.config.timeout_seconds)
        self.downloader = VideoDownloader(self.config, self.http, registry=get_default_registry())
        self.queue = DownloadQueue()
        self.scheduler = TaskScheduler(
            self.queue,
            worker_count=self.config.max_concurrent_downloads,
            executor_fn=self._run_task,
        )
        self._lock = threading.Lock()

    def close(self) -> None:
        self.scheduler.shutdown(wait=False)
        self.downloader.close()
        self.http.close()

    def enqueue_url(
        self,
        url: str,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        output_dir: Optional[Path] = None,
        preferred_height: Optional[int] = None,
        output_format: str = "mp4",
        live: bool = False,
    ) -> str:
        task = DownloadTask(
            url=url,
            output_dir=output_dir or self.config.download_dir,
            priority=priority,
            preferred_height=preferred_height,
            output_format=output_format,
            live=live,
        )
        return self.queue.put(task)

    def expand_playlist_or_channel(
        self,
        seed_url: str,
        *,
        max_urls: int = 200,
        crawl: bool = True,
    ) -> List[str]:
        """
        Collect related video URLs from an extractor's ``discover_related`` hook
        and optional light HTML link extraction for generic pages.
        """
        reg = self.downloader.registry
        ex = reg.pick(seed_url)
        if not ex:
            return [seed_url]
        ctx = ExtractorContext(self.http, self.config)
        urls: List[str] = []
        seen: Set[str] = set()

        def add(u: str) -> None:
            u = u.split("#")[0]
            if u in seen or len(urls) >= max_urls:
                return
            seen.add(u)
            urls.append(u)

        add(seed_url)
        try:
            for seed in ex.discover_related(seed_url, ctx):
                add(seed.url)
        except Exception as exc:
            log.debug("discover_related failed: %s", exc)

        if crawl and len(urls) < max_urls:
            html = self.http.get_text(seed_url)
            for m in re.finditer(r'href="(https?://[^"]+)"', html):
                u = m.group(1)
                if u == seed_url:
                    continue
                if reg.pick(u) is not None:
                    add(u)
                if len(urls) >= max_urls:
                    break

        return urls[:max_urls]

    def start_scheduler(self) -> None:
        self.scheduler.start()

    def pause_all(self) -> None:
        self.queue.pause_all()

    def resume_all(self) -> None:
        self.queue.resume_all()

    def cancel_task(self, task_id: str) -> None:
        self.queue.cancel(task_id)

    def _run_task(self, task: DownloadTask, progress: Optional[ProgressCallback] = None) -> DownloadResult:
        session = DownloadSession(self.downloader)
        if task.cancel_event.is_set():
            raise RuntimeError("cancelled")

        def hook(meta: dict) -> None:
            if progress and task.id:
                # pct unknown for streaming — approximate via indeterminate 0
                speed = meta.get("speed", 0.0)
                progress(task.id, meta.get("pct", 0.0), speed, meta.get("eta", 0.0))

        res = session.run(
            task.url,
            task.output_dir,
            preferred_height=task.preferred_height,
            output_format=task.output_format,
            live=task.live,
            progress=lambda m: hook(m),
            stop_event=task.cancel_event,
        )
        return res


class DownloadManagerPool:
    """Process-oriented placeholder for future multiprocessing scale-out."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def spawn_worker(self) -> None:
        log.info("Multiprocessing pool not enabled in this build.")
