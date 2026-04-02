"""
HLS (HTTP Live Streaming) playlist parsing.

This module implements a practical subset of RFC 8216:

- ``EXT-X-VERSION``, ``EXTINF``, ``EXT-X-TARGETDURATION``, ``EXT-X-MEDIA-SEQUENCE``
- ``EXT-X-ENDLIST`` for VOD playlists
- Master playlists with ``EXT-X-STREAM-INF`` (bandwidth, resolution)
- Relative and absolute segment URIs resolved against the playlist URL

Encrypted streams (``EXT-X-KEY``) are detected: decryption is **not** implemented.
Callers should surface a clear error when encryption is required.

The parser is intentionally forgiving of minor provider quirks (leading BOM,
trailing whitespace on tags) because production playlists are not always
byte-perfect to the letter of the RFC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from ..utils.logger import get_logger

log = get_logger("hls")


@dataclass
class HLSSegment:
    """A single media segment reference from a media playlist."""

    uri: str
    duration: float
    title: str = ""
    byte_range: Optional[Tuple[int, Optional[int]]] = None  # start, length (None = to EOF)


@dataclass
class VariantStream:
    """One row from a master playlist."""

    uri: str
    bandwidth: Optional[int]
    average_bandwidth: Optional[int]
    resolution: Optional[Tuple[int, int]]
    codecs: Optional[str]
    frame_rate: Optional[float]


@dataclass
class MediaPlaylist:
    """Parsed media playlist (not master)."""

    uri: str
    version: Optional[int]
    target_duration: Optional[float]
    media_sequence: int
    endlist: bool
    segments: List[HLSSegment] = field(default_factory=list)
    is_encrypted: bool = False
    encryption_method: Optional[str] = None


@dataclass
class MasterPlaylist:
    uri: str
    variants: List[VariantStream] = field(default_factory=list)


class HLSParser:
    """Stateful parser for `.m3u8` text."""

    _TAG = re.compile(r"#(?P<name>EXT[^:]*)(?::(?P<attrs>.*))?")

    def parse(self, text: str, base_url: str) -> Tuple[Optional[MasterPlaylist], Optional[MediaPlaylist]]:
        text = text.lstrip("\ufeff").strip()
        if not text.startswith("#EXTM3U"):
            raise ValueError("Invalid HLS document: missing #EXTM3U header")

        lines = [ln.strip("\r") for ln in text.splitlines() if ln.strip() != ""]
        # Detect master vs media by presence of EXT-X-STREAM-INF before any segment line
        is_master = any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines)
        if is_master:
            return self._parse_master(lines, base_url), None
        return None, self._parse_media(lines, base_url)

    def _parse_master(self, lines: List[str], base_url: str) -> MasterPlaylist:
        variants: List[VariantStream] = []
        pending_attrs: Optional[str] = None
        for ln in lines:
            if ln.startswith("#EXT-X-STREAM-INF"):
                pending_attrs = ln.split(":", 1)[1] if ":" in ln else ""
                continue
            if ln.startswith("#"):
                continue
            if pending_attrs is not None:
                attrs = self._parse_attr_list(pending_attrs)
                uri = urljoin(base_url + ("/" if not base_url.endswith("/") else ""), ln)
                variants.append(
                    VariantStream(
                        uri=uri,
                        bandwidth=attrs.get("BANDWIDTH"),
                        average_bandwidth=attrs.get("AVERAGE-BANDWIDTH"),
                        resolution=self._parse_resolution(attrs.get("RESOLUTION")),
                        codecs=attrs.get("CODECS"),
                        frame_rate=attrs.get("FRAME-RATE"),
                    )
                )
                pending_attrs = None
        return MasterPlaylist(uri=base_url, variants=variants)

    def _parse_media(self, lines: List[str], base_url: str) -> MediaPlaylist:
        version: Optional[int] = None
        target_duration: Optional[float] = None
        media_sequence = 0
        endlist = False
        segments: List[HLSSegment] = []
        encrypted = False
        enc_method: Optional[str] = None
        pending_duration: Optional[float] = None
        pending_title = ""
        pending_byterange: Optional[Tuple[int, Optional[int]]] = None

        for ln in lines:
            if ln == "#EXTM3U":
                continue
            m = self._TAG.match(ln)
            if m:
                name = m.group("name")
                attrs_raw = m.group("attrs") or ""
                if name == "EXT-X-VERSION":
                    try:
                        version = int(attrs_raw)
                    except ValueError:
                        log.debug("Bad EXT-X-VERSION: %s", attrs_raw)
                elif name == "EXT-X-TARGETDURATION":
                    try:
                        target_duration = float(attrs_raw)
                    except ValueError:
                        pass
                elif name == "EXT-X-MEDIA-SEQUENCE":
                    try:
                        media_sequence = int(attrs_raw)
                    except ValueError:
                        pass
                elif name == "EXT-X-ENDLIST":
                    endlist = True
                elif name == "EXTINF":
                    # format: duration[,title]
                    dur_part, _, rest = attrs_raw.partition(",")
                    try:
                        pending_duration = float(dur_part)
                    except ValueError:
                        pending_duration = None
                    pending_title = rest.strip()
                elif name == "EXT-X-BYTERANGE":
                    # n[@o]
                    pending_byterange = self._parse_byterange(attrs_raw)
                elif name == "EXT-X-KEY":
                    amap = self._parse_attr_list(attrs_raw)
                    method = amap.get("METHOD")
                    enc_method = method
                    if method and method.upper() != "NONE":
                        encrypted = True
                continue

            if ln.startswith("#"):
                continue

            # URI line
            if pending_duration is None:
                log.debug("Skipping orphan URI without EXTINF: %s", ln[:80])
                continue
            uri = urljoin(
                base_url if base_url.endswith("/") else base_url + "/",
                ln,
            )
            segments.append(
                HLSSegment(
                    uri=uri,
                    duration=pending_duration,
                    title=pending_title,
                    byte_range=pending_byterange,
                )
            )
            pending_duration = None
            pending_title = ""
            pending_byterange = None

        return MediaPlaylist(
            uri=base_url,
            version=version,
            target_duration=target_duration,
            media_sequence=media_sequence,
            endlist=endlist,
            segments=segments,
            is_encrypted=encrypted,
            encryption_method=enc_method,
        )

    @staticmethod
    def _parse_byterange(raw: str) -> Tuple[int, Optional[int]]:
        if "@" in raw:
            length_s, start_s = raw.split("@", 1)
            return int(start_s), int(length_s)
        return 0, int(raw)

    @staticmethod
    def _parse_resolution(val: Optional[str]) -> Optional[Tuple[int, int]]:
        if not val or "x" not in val.lower():
            return None
        w, _, h = val.partition("x")
        try:
            return int(w), int(h)
        except ValueError:
            return None

    @staticmethod
    def _parse_attr_list(raw: str) -> Dict[str, Any]:
        """
        Parse HLS attribute lists: key=value pairs separated by commas.

        Values may be quoted. Unquoted numeric values are returned as int/float.
        """
        result: Dict[str, Any] = {}
        i = 0
        n = len(raw)
        key = ""
        while i < n:
            while i < n and raw[i] in " \t":
                i += 1
            eq = raw.find("=", i)
            if eq < 0:
                break
            key = raw[i:eq].strip()
            i = eq + 1
            if i < n and raw[i] == '"':
                i += 1
                start = i
                while i < n and raw[i] != '"':
                    i += 1
                val = raw[start:i]
                i += 1  # skip closing quote
            else:
                start = i
                while i < n and raw[i] != ",":
                    i += 1
                val = raw[start:i].strip()
            # type coercion for known numeric keys
            if key in {"BANDWIDTH", "AVERAGE-BANDWIDTH"}:
                try:
                    val = int(val)
                except ValueError:
                    pass
            if key == "FRAME-RATE":
                try:
                    val = float(val)
                except ValueError:
                    pass
            result[key] = val
            while i < n and raw[i] in " \t,":
                i += 1
        return result

    @staticmethod
    def pick_variant_for_height(master: MasterPlaylist, preferred_height: int) -> Optional[VariantStream]:
        if not master.variants:
            return None
        scored: List[Tuple[int, VariantStream]] = []
        for v in master.variants:
            h = v.resolution[1] if v.resolution else 0
            # Prefer closest height at or below preferred, else smallest above
            if h == 0 and v.bandwidth:
                scored.append((10_000_000 - v.bandwidth, v))
            else:
                delta = abs(h - preferred_height)
                if h > preferred_height:
                    delta += 5000
                scored.append((delta, v))
        scored.sort(key=lambda t: t[0])
        return scored[0][1]


# --- Optional analytics (same module to avoid extra deployment units) ---


@dataclass
class HLSMediaStats:
    """Aggregate statistics for a parsed **media** playlist (not master)."""

    segment_count: int
    total_duration_seconds: float
    estimated_discontinuities: int
    target_duration: Optional[float]


def summarize_media_playlist(pl: MediaPlaylist) -> HLSMediaStats:
    """
    Summarize segment timing. ``estimated_discontinuities`` is reserved for a
    future raw-line scan that counts ``EXT-X-DISCONTINUITY`` markers explicitly.
    """
    total = sum(s.duration for s in pl.segments)
    return HLSMediaStats(
        segment_count=len(pl.segments),
        total_duration_seconds=total,
        estimated_discontinuities=0,
        target_duration=pl.target_duration,
    )


def is_likely_hls_url(url: str) -> bool:
    u = urlparse(url)
    return u.path.endswith(".m3u8") or ".m3u8" in u.path
