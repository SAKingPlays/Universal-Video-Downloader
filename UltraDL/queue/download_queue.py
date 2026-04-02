"""
Priority download queue with pause/resume/cancel semantics.

Tasks carry a ``threading.Event`` used for cooperative cancellation—the
scheduler polls this between segments. ``TaskState`` transitions are linear
with the exception of ``PAUSED`` ↔ ``QUEUED`` moves orchestrated by the user.

Thread-safety: all public methods acquire an internal lock.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional


class TaskPriority(int, Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1


class TaskState(Enum):
    QUEUED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(order=True)
class _PrioItem:
    sort_key: int
    seq: int
    task_id: str = field(compare=False)


@dataclass
class DownloadTask:
    url: str
    output_dir: Path
    priority: TaskPriority = TaskPriority.NORMAL
    preferred_height: Optional[int] = None
    output_format: str = "mp4"
    live: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: TaskState = TaskState.QUEUED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    error: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        # pause_event set => allowed to run; clear => paused mid-flight
        self.pause_event.set()


class DownloadQueue:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._heap: List[_PrioItem] = []
        self._tasks: Dict[str, DownloadTask] = {}
        self._seq = itertools.count()
        self._paused_globally = False

    def put(self, task: DownloadTask) -> str:
        with self._lock:
            self._tasks[task.id] = task
            heapq.heappush(
                self._heap,
                _PrioItem(int(task.priority), next(self._seq), task.id),
            )
            return task.id

    def get_next(self, timeout: Optional[float] = None) -> Optional[DownloadTask]:
        deadline = None if timeout is None else (__import__("time").monotonic() + timeout)
        while True:
            with self._lock:
                if self._paused_globally or not self._heap:
                    item = None
                else:
                    item = heapq.heappop(self._heap)
                task = self._tasks[item.task_id] if item else None
                if task and task.state == TaskState.CANCELLED:
                    continue
                if task and task.state == TaskState.PAUSED:
                    heapq.heappush(self._heap, item)
                    task = None
                if task:
                    task.state = TaskState.RUNNING
                    return task
            if timeout is not None:
                now = __import__("time").monotonic()
                if now >= deadline:  # type: ignore
                    return None
            threading.Event().wait(0.05)

    def pause_all(self) -> None:
        with self._lock:
            self._paused_globally = True

    def resume_all(self) -> None:
        with self._lock:
            self._paused_globally = False

    def pause_task(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return
            t.pause_event.clear()
            if t.state == TaskState.QUEUED:
                t.state = TaskState.PAUSED

    def resume_task(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return
            t.pause_event.set()
            if t.state == TaskState.PAUSED:
                t.state = TaskState.QUEUED
                heapq.heappush(self._heap, _PrioItem(int(t.priority), next(self._seq), t.id))

    def cancel(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return
            t.cancel_event.set()
            t.state = TaskState.CANCELLED

    def complete(self, task_id: str, *, error: Optional[str] = None) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return
            if error:
                t.state = TaskState.FAILED
                t.error = error
            else:
                t.state = TaskState.COMPLETED

    def snapshot(self) -> List[DownloadTask]:
        with self._lock:
            return list(self._tasks.values())
