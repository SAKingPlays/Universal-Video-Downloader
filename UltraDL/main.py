#!/usr/bin/env python3
"""
UltraDL entrypoint.

From the parent directory of the ``UltraDL`` package (project root)::

    python -m UltraDL.main "https://www.youtube.com/watch?v=..."

Or after ``pip install -e .`` (if you add a setuptools stanza), simply
``ultradl`` on PATH.

Direct script execution also works::

    python UltraDL/main.py "https://..."
"""

from __future__ import annotations

import sys
from pathlib import Path

# Important: prevent `UltraDL/queue` from shadowing the stdlib `queue` module.
# This can happen when running `python main.py` *from inside* the `UltraDL/` folder.
_PKG_DIR = Path(__file__).resolve().parent
_ROOT = _PKG_DIR.parent
_PKG_DIR_STR = str(_PKG_DIR)
if _PKG_DIR_STR in sys.path:
    sys.path.remove(_PKG_DIR_STR)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from UltraDL.interface.cli import run_cli  # noqa: E402


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
