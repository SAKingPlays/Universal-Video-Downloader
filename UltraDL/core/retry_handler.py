"""
Configurable retry policies for network segmentation.

UltraDL distinguishes **idempotent** GET segment fetches (safe to retry) from
**single-flight** operations such as finalize-to-disk where duplicates would
corrupt output. Policies use exponential backoff with jitter to reduce thundering
herd effects when a CDN hiccups.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int = 5
    base_delay: float = 0.5
    max_delay: float = 30.0


class RetryHandler:
    def __init__(self, policy: RetryPolicy) -> None:
        self.policy = policy

    def run(
        self,
        fn: Callable[[], T],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
    ) -> T:
        attempt = 0
        while True:
            attempt += 1
            try:
                return fn()
            except retry_on:
                if attempt >= self.policy.max_attempts:
                    raise
                delay = min(
                    self.policy.max_delay,
                    self.policy.base_delay * (2 ** (attempt - 1)),
                )
                delay *= 0.75 + random.random() * 0.5
                time.sleep(delay)
