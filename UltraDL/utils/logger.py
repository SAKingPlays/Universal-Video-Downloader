"""
Structured logging for UltraDL.

UltraDL uses a two-layer logging strategy:
- Library code logs through ``logging`` so integrators can attach their own handlers.
- The CLI attaches Rich-backed handlers for readable console output.

Rotating file handlers capture high-volume debug traces without filling the disk.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    Configure the root UltraDL logger hierarchy.

    ``log_file`` enables a rotating file sink. Console logging is left to
    application code (for example the Rich handler in ``interface/cli.py``)
    so GUI mode stays quiet unless explicitly configured.
    """
    root = logging.getLogger("ultradl")
    root.setLevel(level)
    root.handlers.clear()

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(fh)

    # Minimal stderr fallback for early bootstrap errors
    if not root.handlers:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(level)
        sh.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``ultradl`` namespace."""
    return logging.getLogger(f"ultradl.{name}")

