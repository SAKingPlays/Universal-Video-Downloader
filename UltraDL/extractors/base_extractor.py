"""
Extractor framework: every site is a plugin implementing ``BaseExtractor``.

Design goals
------------

1. **URL dispatch** — ``ExtractorRegistry`` scores candidate extractors so that
   specialized modules beat generic HTML heuristics.

2. **Normalized output** — each extractor returns ``ExtractedVideo`` describing
   progressive URLs, HLS/DASH manifests, and crawl seeds (playlists/channels).

3. **Isolation** — extractors receive a narrow ``ExtractorContext`` with HTTP
   access and configuration, not the entire download manager. That boundary keeps
   tests small and avoids circular imports.

Adding a new site
-----------------

Subclass ``BaseExtractor``, implement ``match_score`` and ``extract``, then
register with ``ExtractorRegistry.register``. Core code never edits dispatch
tables when a new module is added.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Sequence
from urllib.parse import urlparse

from ..utils.config_loader import AppConfig
from ..utils.network_utils import HTTPClient


class StreamKind(Enum):
    PROGRESSIVE = auto()
    HLS = auto()
    DASH = auto()
    WEBRTC_HINT = auto()  # placeholder for future real-time paths


@dataclass
class StreamCandidate:
    """A single playable stream option."""

    kind: StreamKind
    url: str
    height: Optional[int] = None
    width: Optional[int] = None
    bitrate: Optional[int] = None
    fps: Optional[float] = None
    codecs: Optional[str] = None
    language: Optional[str] = None
    is_hdr: bool = False
    label: str = ""

    def quality_tier(self) -> str:
        h = self.height or 0
        if h >= 2160:
            return "4K"
        if h >= 1440:
            return "1440p"
        if h >= 1080:
            return "1080p"
        if h >= 720:
            return "720p"
        if h >= 480:
            return "480p"
        if h >= 360:
            return "360p"
        if h >= 144:
            return "144p"
        if self.bitrate:
            mbps = self.bitrate / 1_000_000
            return f"{mbps:.1f} Mbps"
        return "unknown"


@dataclass
class CrawlSeed:
    """Hints for playlist/channel expansion."""

    url: str
    title_hint: str = ""


@dataclass
class ExtractedVideo:
    """Canonical extraction payload."""

    canonical_url: str
    title: str
    description: str = ""
    uploader: str = ""
    upload_date: Optional[str] = None  # ISO-8601 date if known
    thumbnail_urls: List[str] = field(default_factory=list)
    subtitles: List["SubtitleRef"] = field(default_factory=list)
    streams: List[StreamCandidate] = field(default_factory=list)
    related_pages: List[CrawlSeed] = field(default_factory=list)
    extractor_id: str = ""
    raw_debug: Dict[str, str] = field(default_factory=dict)


@dataclass
class SubtitleRef:
    url: str
    language: str
    format: str  # vtt|srt|srv3


class ExtractorContext:
    """Services exposed to extractors."""

    def __init__(self, client: HTTPClient, config: AppConfig) -> None:
        self.client = client
        self.config = config


class BaseExtractor(ABC):
    """Site extractor plugin."""

    #: Short stable id, e.g. ``youtube``.
    name: str = "base"

    @abstractmethod
    def match_score(self, url: str) -> int:
        """
        Return 0 if this extractor cannot handle the URL.

        Higher scores win. Typical exclusive domains return 100+; generic HTML
        returns single digits.
        """

    @abstractmethod
    def extract(self, url: str, ctx: ExtractorContext) -> ExtractedVideo:
        """Perform network + parse work and return normalized metadata."""

    def discover_related(self, url: str, ctx: ExtractorContext) -> List[CrawlSeed]:
        """Optional hook for playlist/channel discovery without full extraction."""
        return []


class ExtractorRegistry:
    """
    Ordered extractor registry with simple precedence rules.

    Registration order is preserved as a tie-breaker after score.
    """

    def __init__(self) -> None:
        self._extractors: List[BaseExtractor] = []

    def register(self, extractor: BaseExtractor) -> None:
        self._extractors.append(extractor)

    def candidates(self, url: str) -> List[BaseExtractor]:
        scored = [(e.match_score(url), idx, e) for idx, e in enumerate(self._extractors)]
        scored = [t for t in scored if t[0] > 0]
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [t[2] for t in scored]

    def pick(self, url: str) -> Optional[BaseExtractor]:
        c = self.candidates(url)
        return c[0] if c else None


def get_default_registry() -> ExtractorRegistry:
    """
    Factory wiring built-in extractors.

    Import site modules lazily to avoid import cycles and optional GUI deps.
    """
    reg = ExtractorRegistry()
    from .youtube_extractor import YouTubeExtractor
    from .vimeo_extractor import VimeoExtractor
    from .generic_extractor import GenericHTMLExtractor

    reg.register(YouTubeExtractor())
    reg.register(VimeoExtractor())
    reg.register(GenericHTMLExtractor())  # lowest priority
    return reg


def hostname_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def domain_regex(patterns: Sequence[str]) -> re.Pattern[str]:
    return re.compile("^(" + "|".join(re.escape(p) for p in patterns) + ")$", re.IGNORECASE)
