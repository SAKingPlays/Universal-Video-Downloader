"""
Filesystem helpers: safe names, atomic writes, cache files, and disk checks.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import BinaryIO, Union

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, max_length: int = 180, default: str = "video") -> str:
    """
    Produce a cross-platform filename stem.

    Strips Unicode compatibility formats and replaces characters illegal on
    Windows and POSIX-looking shells.
    """
    name = unicodedata.normalize("NFKC", name).strip()
    name = _INVALID_CHARS.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = default
    return name[:max_length]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_replace(src: Path, dest: Path) -> None:
    """Rename ``src`` to ``dest``, replacing destination if present (best-effort)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def write_atomic(path: Path, data: Union[bytes, str], *, encoding: str = "utf-8") -> None:
    """Write file atomically using a temp file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmppath = tempfile.mkstemp(prefix=".ultradl_", dir=str(path.parent))
    tmp = Path(tmppath)
    try:
        with os.fdopen(fd, "wb" if isinstance(data, bytes) else "w", encoding=None if isinstance(data, bytes) else encoding) as f:
            f.write(data)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def disk_free_bytes(path: Path) -> int:
    """Return free space for the filesystem containing ``path``."""
    usage = shutil.disk_usage(path)
    return int(usage.free)


class SpoolFile:
    """Large binary spool with explicit flush to final path."""

    def __init__(self, final_path: Path) -> None:
        self.final_path = final_path
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmppath = tempfile.mkstemp(prefix=".ultradl_spool_", dir=str(self.final_path.parent))
        self._path = Path(tmppath)
        self._fd: BinaryIO = open(fd, "wb", closefd=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, chunk: bytes) -> None:
        self._fd.write(chunk)

    def tell(self) -> int:
        return self._fd.tell()

    def close_commit(self) -> None:
        self._fd.flush()
        self._fd.close()
        atomic_replace(self._path, self.final_path)

    def close_discard(self) -> None:
        self._fd.close()
        self._path.unlink(missing_ok=True)

