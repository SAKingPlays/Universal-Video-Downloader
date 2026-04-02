"""
Generic HTML extractor — last-resort heuristics.

This extractor scans for:

- OpenGraph ``og:video`` / ``og:video:url``
- ``<video src="...">`` and ``<source src="...">``
- JSON-LD ``VideoObject.embedUrl`` or ``contentUrl``

It intentionally returns **low** ``match_score`` so site-specific extractors win.
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..utils.logger import get_logger
from .base_extractor import (
    BaseExtractor,
    ExtractorContext,
    ExtractedVideo,
    StreamCandidate,
    StreamKind,
)

log = get_logger("extract.generic")


class GenericHTMLExtractor(BaseExtractor):
    name = "generic_html"

    def match_score(self, url: str) -> int:
        scheme = urlparse(url).scheme
        return 1 if scheme in {"http", "https"} else 0

    def extract(self, url: str, ctx: ExtractorContext) -> ExtractedVideo:
        html = ctx.client.get_text(url)
        soup = BeautifulSoup(html, "html.parser")
        streams: List[StreamCandidate] = []
        title = (soup.title.string or "Video").strip() if soup.title else "Video"

        def add(u: Optional[str], label: str) -> None:
            if not u:
                return
            u = u.strip()
            if not u or u.startswith("javascript:"):
                return
            absu = urljoin(url, u)
            kind = StreamKind.HLS if ".m3u8" in absu else StreamKind.PROGRESSIVE
            streams.append(StreamCandidate(kind=kind, url=absu, label=label))

        # Meta tags
        for prop in ("og:video:secure_url", "og:video:url", "og:video"):
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                add(tag["content"], prop)

        # video tag
        for v in soup.find_all("video"):
            add(v.get("src"), "video-src")
            for s in v.find_all("source"):
                add(s.get("src"), "video-source")

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                blob = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue
            for node in self._walk_ld(blob):
                if node.get("@type") in {"VideoObject", "http://schema.org/VideoObject"}:
                    add(node.get("embedUrl"), "ld-embed")
                    add(node.get("contentUrl"), "ld-content")

        # Raw regex fallback for URLs ending in mp4/webm/m3u8
        for m in re.finditer(
            r'https?://[^\s"\'<>]+\.(?:mp4|webm|m3u8)(?:\?[^\s"\'<>]+)?',
            html,
            re.IGNORECASE,
        ):
            add(unescape(m.group(0)), "regex")

        # Dedup by URL
        seen = set()
        uniq: List[StreamCandidate] = []
        for s in streams:
            if s.url in seen:
                continue
            seen.add(s.url)
            uniq.append(s)

        if not uniq:
            raise RuntimeError("Generic extractor could not locate a video URL in the page.")

        return ExtractedVideo(
            canonical_url=url,
            title=title,
            streams=uniq,
            extractor_id=self.name,
        )

    def _walk_ld(self, obj: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if isinstance(obj, dict):
            out.append(obj)
            for v in obj.values():
                out.extend(self._walk_ld(v))
        elif isinstance(obj, list):
            for v in obj:
                out.extend(self._walk_ld(v))
        return out
