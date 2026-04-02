"""
MPEG-DASH MPD parser (XML) — practical subset for on-demand content.

UltrDL supports:
- ``BaseURL`` elements (single level, with ``@serviceLocation`` ignored)
- ``AdaptationSet`` with video ``mimeType`` / ``contentType``
- ``Representation`` with ``@width``, ``@height``, ``@bandwidth``, ``@codecs``
- SegmentTemplate with ``$Number$`` or ``$Time$`` media URLs
- Multi-period MPDs: **first period only** for simplicity (extend as needed)

DRM ``ContentProtection`` nodes are noticed; encrypted representations raise
a clear error path for callers.

Namespaces are handled via wildcard local-name matching because providers use
different xmlns URIs inconsistently.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from ..utils.logger import get_logger

log = get_logger("dash")


_NS_WILDCARD = "*"


def _local(tag: str) -> str:
    return f"{_NS_WILDCARD}{tag}"


@dataclass
class DASHSegment:
    url: str
    duration_seconds: Optional[float] = None


@dataclass
class Representation:
    id: str
    mime_type: Optional[str]
    codecs: Optional[str]
    bandwidth: Optional[int]
    width: Optional[int]
    height: Optional[int]
    initialization_range: Optional[Tuple[int, int]]
    media_template: str
    start_number: int
    timescale: Optional[int]
    segment_duration: Optional[int]  # in timescale units
    segments: List[DASHSegment] = field(default_factory=list)
    content_protected: bool = False


@dataclass
class DASHManifest:
    source_url: str
    representations: List[Representation] = field(default_factory=list)


class DASHParser:
    def parse_text(self, xml_text: str, base_url: str) -> DASHManifest:
        root = ET.fromstring(xml_text)
        return self._parse_root(root, base_url)

    def _parse_root(self, root: ET.Element, base_url: str) -> DASHManifest:
        # Depth-first BaseURL resolution (first wins per level)
        def base_for(elem: ET.Element, inherited: str) -> str:
            for child in elem:
                if self._tag(child) == "BaseURL":
                    text = (child.text or "").strip()
                    return urljoin(inherited, text)
            return inherited

        mpd_duration = root.attrib.get("mediaPresentationDuration")
        mpd_dur_sec = self._parse_iso_duration_seconds(mpd_duration) if mpd_duration else None

        period = None
        for child in root:
            if self._tag(child) == "Period":
                period = child
                break
        if period is None:
            raise ValueError("MPD missing Period element")

        period_base = base_for(period, base_for(root, base_url))
        period_dur_attr = period.attrib.get("duration")
        period_dur_sec = (
            self._parse_iso_duration_seconds(period_dur_attr) if period_dur_attr else None
        )
        content_duration = period_dur_sec or mpd_dur_sec

        reps: List[Representation] = []
        for child in period:
            if self._tag(child) != "AdaptationSet":
                continue
            adap_base = base_for(child, period_base)
            mime = child.attrib.get("mimeType")
            content_type = child.attrib.get("contentType")
            protected = any(self._tag(g) == "ContentProtection" for g in child)
            for rep in child:
                if self._tag(rep) != "Representation":
                    continue
                r = self._parse_representation(
                    rep, adap_base, mime, content_type, protected, content_duration
                )
                if r is not None:
                    reps.append(r)
        return DASHManifest(source_url=base_url, representations=reps)

    def _tag(self, elem: ET.Element) -> str:
        if elem.tag.startswith("{"):
            return elem.tag.split("}", 1)[1]
        return elem.tag

    def _parse_representation(
        self,
        rep: ET.Element,
        base: str,
        parent_mime: Optional[str],
        parent_content: Optional[str],
        parent_protected: bool,
        content_duration_seconds: Optional[float],
    ) -> Optional[Representation]:
        rid = rep.attrib.get("id", "")
        mime = rep.attrib.get("mimeType") or parent_mime
        codecs = rep.attrib.get("codecs")
        bandwidth = rep.attrib.get("bandwidth")
        width = rep.attrib.get("width")
        height = rep.attrib.get("height")
        protected = parent_protected or any(self._tag(c) == "ContentProtection" for c in rep)

        rep_base = base
        for c in rep:
            if self._tag(c) == "BaseURL":
                rep_base = urljoin(rep_base, (c.text or "").strip())
                break

        init_range: Optional[Tuple[int, int]] = None
        media_template: Optional[str] = None
        start_number = 1
        timescale: Optional[int] = None
        seg_dur: Optional[int] = None
        explicit_segments: List[DASHSegment] = []

        for c in rep:
            tag = self._tag(c)
            if tag == "SegmentBase":
                init = next((x for x in c if self._tag(x) == "Initialization"), None)
                if init is not None:
                    ir = init.attrib.get("range")
                    if ir and "-" in ir:
                        a, b = ir.split("-", 1)
                        init_range = (int(a), int(b))
                # Single URL might be entire file
                continue
            if tag == "SegmentList":
                duration = c.attrib.get("duration")
                ts = c.attrib.get("timescale")
                if ts:
                    timescale = int(ts)
                if duration:
                    seg_dur = int(duration)
                for seg in c:
                    if self._tag(seg) == "SegmentURL":
                        media = seg.attrib.get("media")
                        if media:
                            explicit_segments.append(DASHSegment(url=urljoin(rep_base, media)))
                continue
            if tag == "SegmentTemplate":
                media_template = c.attrib.get("media")
                init_t = c.attrib.get("initialization")
                sn = c.attrib.get("startNumber")
                if sn:
                    try:
                        start_number = int(sn)
                    except ValueError:
                        pass
                ts = c.attrib.get("timescale")
                if ts:
                    timescale = int(ts)
                sd = c.attrib.get("duration")
                if sd:
                    try:
                        seg_dur = int(sd)
                    except ValueError:
                        pass
                # SegmentTimeline support: enumerate explicit URLs
                stl = next((x for x in c if self._tag(x) == "SegmentTimeline"), None)
                if stl is not None and media_template and "$Time$" in media_template:
                    t = 0
                    for se in stl:
                        if self._tag(se) != "S":
                            continue
                        d = int(se.attrib.get("d", "0"))
                        r = int(se.attrib.get("r", "0"))
                        t_attr = se.attrib.get("t")
                        if t_attr is not None:
                            t = int(t_attr)
                        count = r + 1
                        for _ in range(count):
                            url = self._substitute_time(media_template, t)
                            explicit_segments.append(
                                DASHSegment(url=urljoin(rep_base, url), duration_seconds=d / (timescale or 1))
                            )
                            t += d
                continue

        if mime and parent_content == "audio" and not (width or height):
            # Caller may filter video separately; we still attach dimensions if present
            pass

        if not media_template and not explicit_segments:
            # Some manifests use SegmentBase only (single file) — treat as progressive URL
            if init_range is None:
                return None
            # initialization + index-less progressive edge case: skip
            return None

        template_resolved_start = rep_base
        if media_template and "$Number$" in media_template and not explicit_segments:
            # Materialize first N segments using duration and MPD mediaPresentationDuration if possible
            count = self._estimate_segment_count(seg_dur, timescale, content_duration_seconds)
            for i in range(start_number, start_number + count):
                path = self._substitute_number(media_template, i)
                explicit_segments.append(DASHSegment(url=urljoin(rep_base, path)))

        if not explicit_segments:
            return None

        return Representation(
            id=rid,
            mime_type=mime,
            codecs=codecs,
            bandwidth=int(bandwidth) if bandwidth else None,
            width=int(width) if width else None,
            height=int(height) if height else None,
            initialization_range=init_range,
            media_template=media_template or "",
            start_number=start_number,
            timescale=timescale,
            segment_duration=seg_dur,
            segments=explicit_segments,
            content_protected=protected,
        )

    @staticmethod
    def _substitute_number(template: str, number: int) -> str:
        return template.replace("$Number$", str(number))

    @staticmethod
    def _substitute_time(template: str, time_value: int) -> str:
        return template.replace("$Time$", str(time_value))

    def _estimate_segment_count(
        self,
        seg_dur: Optional[int],
        timescale: Optional[int],
        period_duration: Optional[float],
    ) -> int:
        if seg_dur and timescale and period_duration and seg_dur > 0:
            return max(1, int(period_duration * timescale / seg_dur) + 2)
        return 5000  # safe upper bound for live; caller should stop on 404

    @staticmethod
    def _parse_iso_duration_seconds(dur: str) -> float:
        # PT1H2M3.4S
        m = re.match(
            r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?",
            dur,
        )
        if not m:
            return 0.0
        h = float(m.group("h") or 0)
        mi = float(m.group("m") or 0)
        s = float(m.group("s") or 0)
        return h * 3600 + mi * 60 + s

    @staticmethod
    def pick_representation_for_height(manifest: DASHManifest, preferred_height: int) -> Optional[Representation]:
        video_reps = [
            r
            for r in manifest.representations
            if r.height and r.mime_type and "video" in r.mime_type
        ]
        if not video_reps:
            video_reps = [r for r in manifest.representations if r.height]
        if not video_reps:
            return None

        def score(r: Representation) -> Tuple[int, int]:
            h = r.height or 0
            delta = abs(h - preferred_height)
            penalty = 5000 if h > preferred_height else 0
            bw = -(r.bandwidth or 0)
            return delta + penalty, bw

        return sorted(video_reps, key=score)[0]
