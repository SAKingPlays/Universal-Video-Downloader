"""
Vimeo public video page extractor.

Vimeo embeds a ``config`` URL or inline ``window.playerConfig`` JSON on many
watch pages. UltraDL walks those structures to find progressive files and HLS.

Private videos, DRM, and login walls are out of scope and will fail with a
clear exception.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..utils.logger import get_logger
from .base_extractor import (
    BaseExtractor,
    CrawlSeed,
    ExtractorContext,
    ExtractedVideo,
    StreamCandidate,
    StreamKind,
    hostname_of,
)

log = get_logger("extract.vimeo")


class VimeoExtractor(BaseExtractor):
    name = "vimeo"

    def match_score(self, url: str) -> int:
        host = hostname_of(url)
        if host in {"vimeo.com", "player.vimeo.com"}:
            return 110
        return 0

    def extract(self, url: str, ctx: ExtractorContext) -> ExtractedVideo:
        html = ctx.client.get_text(url, headers={"Referer": url})
        cfg_url = self._find_config_url(html)
        data: Dict[str, Any]
        if cfg_url:
            jtxt = ctx.client.get_text(cfg_url, headers={"Referer": url})
            data = json.loads(jtxt)
        else:
            embedded = self._extract_inline_config(html)
            if embedded is None:
                raise RuntimeError("Vimeo player config not found — page may require login or use DRM.")
            data = embedded

        video = data.get("video") or {}
        title = video.get("title") or "Vimeo video"
        desc = video.get("description") or ""
        user = ((video.get("owner") or {}).get("name")) or ""
        thumbs: List[str] = []
        for p in video.get("thumbs") or {}:
            t = (video.get("thumbs") or {}).get(p, {}).get("base")
            if isinstance(t, str):
                thumbs.append(t + "_960.jpg")

        streams: List[StreamCandidate] = []

        # Progressive files — ``file.progressive`` when present
        file_block = video.get("download") or video.get("play") or {}
        prog = None
        if isinstance(file_block, dict):
            prog = file_block.get("progressive") or video.get("download")
        if isinstance(prog, list):
            for p in prog:
                url_p = p.get("link")
                if not url_p:
                    continue
                streams.append(
                    StreamCandidate(
                        kind=StreamKind.PROGRESSIVE,
                        url=url_p,
                        height=p.get("height"),
                        width=p.get("width"),
                        bitrate=p.get("bitrate"),
                        label=f"{p.get('quality')}",
                    )
                )

        # HLS: search in request.files.hls.cdns
        files = ((video.get("files") or {}).get("hls") or {}).get("cdns") or {}
        for _cdn, cinfo in files.items():
            hls_cdns = cinfo.get("url") if isinstance(cinfo, dict) else None
            if hls_cdns:
                streams.append(StreamCandidate(kind=StreamKind.HLS, url=hls_cdns, label="hls"))

        # Fallback: dashjp in some payloads
        dash = ((video.get("files") or {}).get("dash") or {}).get("cdns") or {}
        for _cdn, cinfo in dash.items():
            link = cinfo.get("url") if isinstance(cinfo, dict) else None
            if link and link.endswith(".mpd"):
                streams.append(StreamCandidate(kind=StreamKind.DASH, url=link, label="dash"))

        related: List[CrawlSeed] = []
        return ExtractedVideo(
            canonical_url=url,
            title=title,
            description=desc,
            uploader=user,
            thumbnail_urls=thumbs,
            streams=streams,
            related_pages=related,
            extractor_id=self.name,
        )

    def _find_config_url(self, html: str) -> Optional[str]:
        m = re.search(r'data-config-url="([^"]+)"', html)
        if m:
            return m.group(1).replace("&amp;", "&")
        m = re.search(r'"config_url"\s*:\s*"([^"]+)"', html)
        if m:
            raw = m.group(1).replace("\\/", "/")
            return raw.encode("utf-8").decode("unicode_escape")
        return None

    def _extract_inline_config(self, html: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"window\.playerConfig\s*=\s*(\{.+?\})\s*;", html, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
