#!/usr/bin/env python3
"""Developer convenience launcher (identical to ``UltraDL/main.py``)."""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent  # UltraDL/
_ROOT = _PKG_DIR.parent
_PKG_DIR_STR = str(_PKG_DIR)
if _PKG_DIR_STR in sys.path:
    sys.path.remove(_PKG_DIR_STR)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from UltraDL.interface.cli import run_cli  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_cli())
