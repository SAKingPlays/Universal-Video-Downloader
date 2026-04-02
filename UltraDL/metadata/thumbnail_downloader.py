"""Download best-effort thumbnail images next to the output video."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..utils.logger import get_logger
from ..utils.network_utils import HTTPClient

log = get_logger("thumbnail")


class ThumbnailDownloader:
    def __init__(self, client: HTTPClient) -> None:
        self._client = client

    def download_best(self, urls: List[str], dest_stem: Path) -> Optional[Path]:
        """
        Try URLs in order; save first success as ``dest_stem.jpg``.

        Returns saved path or ``None`` if all attempts fail.
        """
        out = dest_stem.with_suffix(".jpg")
        for u in urls:
            try:
                res = self._client.get_bytes(u)
                if res.status_code != 200 or not res.content:
                    continue
                out.write_bytes(res.content)
                log.info("Saved thumbnail %s", out)
                return out
            except Exception as exc:
                log.debug("Thumbnail fetch failed %s: %s", u, exc)
        return None
