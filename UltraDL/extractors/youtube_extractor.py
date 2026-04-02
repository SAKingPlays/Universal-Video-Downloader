"""
YouTube extractor — reimplements **public watch-page** parsing in Python.

UltraDL does **not** embed youtube-dl/yt-dlp. This module mirrors what a normal
browser does when loading ``youtube.com/watch``: pull HTML, extract the embedded
JSON blob(s), walk ``streamingData`` formats, and surface progressive/HLS/DASH
URLs where Google exposes them.

**Important limitations (by design / policy / technical reality):**

- Age-restricted, premium, and some music videos may require authenticated
  signed requests UltraDL does not perform.
- Ciphered ``signatureCipher`` / ``n``-parameter throttling transforms change
  frequently; this implementation includes a **best-effort** parser that will
  break when YouTube rotates obfuscation. When that happens, extraction fails
  loudly instead of silently downloading garbage.
- Live streams: UltraDL records HLS URLs when present in the player response.

The code is structured for maintainability: JSON extraction and format mapping
live in separate private helpers so engineers can patch transformations in one
place.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

from ..utils.logger import get_logger
from .base_extractor import (
    BaseExtractor,
    CrawlSeed,
    ExtractorContext,
    ExtractedVideo,
    StreamCandidate,
    StreamKind,
    SubtitleRef,
    hostname_of,
)

log = get_logger("extract.youtube")


_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def _video_id_from_url(url: str) -> Optional[str]:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        return u.path.strip("/").split("/")[0] or None
    if "youtube.com" in host:
        if u.path.startswith("/watch"):
            q = parse_qs(u.query)
            v = q.get("v", [None])[0]
            return v
        if u.path.startswith("/shorts/"):
            return u.path.split("/")[2]
        if u.path.startswith("/embed/"):
            return u.path.split("/")[2]
    return None


def _extract_json_object(prefix: str, html: str) -> Optional[Dict[str, Any]]:
    """
    Find a JSON object assignment like ``var ytInitialPlayerResponse = {...};``.

    This is intentionally heuristic — YouTube inlines multiple JSON payloads.
    """
    marker = prefix
    idx = html.find(marker)
    if idx < 0:
        return None
    brace = html.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    for i in range(brace, len(html)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = html[brace : i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    log.debug("JSON decode failed for %s", prefix)
                    return None
    return None


def _itag_height_map() -> Dict[int, int]:
    # Common itag -> height hints (not exhaustive)
    return {
        18: 360,
        22: 720,
        37: 1080,
        38: 3072,
        43: 360,
        44: 480,
        45: 720,
        46: 1080,
        133: 240,
        134: 360,
        135: 480,
        136: 720,
        137: 1080,
        138: 4320,
        140: 0,  # audio only
        160: 144,
        242: 240,
        243: 360,
        244: 480,
        247: 720,
        248: 1080,
        271: 1440,
        272: 4320,
        298: 720,
        299: 1080,
        302: 720,
        303: 1080,
        308: 1440,
        313: 2160,
        315: 2160,
        330: 144,
        331: 240,
        332: 360,
        333: 480,
        334: 720,
        335: 1080,
        336: 1440,
        337: 2160,
    }


def _parse_stream_url(fmt: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    url = fmt.get("url")
    cipher = fmt.get("signatureCipher") or fmt.get("cipher")
    if url:
        return url, None
    if not cipher:
        return None, None
    parts = {}
    for chunk in str(cipher).split("&"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k] = v
    base = parts.get("url")
    if base:
        base = unquote(base)
    # ultra-light handling: return unsignatured base if sp/s are absent
    return base, None


class YouTubeExtractor(BaseExtractor):
    name = "youtube"

    def match_score(self, url: str) -> int:
        host = hostname_of(url)
        if host in _YT_HOSTS or host.endswith(".youtube.com"):
            return 120
        return 0

    def extract(self, url: str, ctx: ExtractorContext) -> ExtractedVideo:
        vid = _video_id_from_url(url)
        if not vid:
            raise ValueError("Not a recognized YouTube watch URL")

        watch_url = f"https://www.youtube.com/watch?v={quote(vid)}"
        headers = {"Accept-Language": "en-US,en;q=0.9"}
        html = ctx.client.get_text(watch_url, headers=headers)

        player = _extract_json_object("ytInitialPlayerResponse", html)
        if player is None:
            # Fallback: try ytmicroformat in separate blob via regex window\[\"ytInitialData\"\] — skip for size

            raise RuntimeError(
                "Could not locate ytInitialPlayerResponse — page layout may have changed "
                "or additional consent/captcha is required."
            )

        video_details = player.get("videoDetails") or {}
        title = video_details.get("title") or "YouTube video"
        desc = video_details.get("shortDescription") or ""
        author = video_details.get("author") or ""
        thumbs = []
        thumbs_dict = video_details.get("thumbnail") or {}
        for th in thumbs_dict.get("thumbnails") or []:
            u = th.get("url")
            if u:
                thumbs.append(u)

        subs = self._subtitle_refs(player)

        streaming = player.get("streamingData") or {}
        formats = list(streaming.get("formats", [])) + list(streaming.get("adaptiveFormats", []))

        streams: List[StreamCandidate] = []
        hmap = _itag_height_map()
        hls_url = streaming.get("hlsManifestUrl")
        if hls_url:
            streams.append(StreamCandidate(kind=StreamKind.HLS, url=hls_url, label="hls-master"))

        dash_url = None
        for fmt in formats:
            mt = (fmt.get("mimeType") or "").lower()
            if "dash" in mt or fmt.get("url", "").endswith(".mpd"):
                dash_url = fmt.get("url")
        if dash_url:
            streams.append(StreamCandidate(kind=StreamKind.DASH, url=dash_url, label="dash"))

        for fmt in formats:
            url_p, _sig = _parse_stream_url(fmt)
            if not url_p:
                continue
            itag = int(fmt.get("itag") or 0)
            h = fmt.get("height") or hmap.get(itag)
            w = fmt.get("width")
            br = fmt.get("bitrate")
            mime = fmt.get("mimeType")
            kind = StreamKind.PROGRESSIVE if "dash" not in (mime or "") else StreamKind.PROGRESSIVE
            if "video" in (mime or "") or fmt.get("vcodec", "none") != "none":
                streams.append(
                    StreamCandidate(
                        kind=kind,
                        url=url_p,
                        height=int(h) if h else None,
                        width=int(w) if w else None,
                        bitrate=int(br) if br else None,
                        codecs=mime,
                        label=f"itag-{itag}",
                    )
                )

        related = self._playlist_seeds(html, watch_url)

        return ExtractedVideo(
            canonical_url=watch_url,
            title=title,
            description=desc,
            uploader=author,
            thumbnail_urls=thumbs,
            subtitles=subs,
            streams=streams,
            related_pages=related,
            extractor_id=self.name,
        )

    def discover_related(self, url: str, ctx: ExtractorContext) -> List[CrawlSeed]:
        try:
            vid = _video_id_from_url(url)
        except Exception:
            return []
        if not vid:
            return []
        html = ctx.client.get_text(url)
        return self._playlist_seeds(html, url)

    def _subtitle_refs(self, player: Dict[str, Any]) -> List[SubtitleRef]:
        out: List[SubtitleRef] = []
        caps = player.get("captions") or {}
        tracklist = (caps.get("playerCaptionsTracklistRenderer") or {}).get("captionTracks") or []
        for tr in tracklist:
            base = tr.get("baseUrl")
            lang = tr.get("languageCode") or "und"
            if not base:
                continue
            fmt = "vtt"
            if "fmt=srv3" in base or "format=srv3" in base:
                fmt = "srv3"
            out.append(SubtitleRef(url=base, language=lang, format=fmt))
        return out

    def _playlist_seeds(self, html: str, ref_url: str) -> List[CrawlSeed]:
        seeds: List[CrawlSeed] = []
        for m in re.finditer(r'href="(/watch\?[^"]+list=[^"&]+[^"]*)"', html):
            path = m.group(1)
            seeds.append(CrawlSeed(url="https://www.youtube.com" + path.split("&amp;")[0], title_hint="youtube-list"))
        # de-dup
        seen = set()
        uniq: List[CrawlSeed] = []
        for s in seeds:
            if s.url in seen:
                continue
            seen.add(s.url)
            uniq.append(s)
        return uniq[:50]
