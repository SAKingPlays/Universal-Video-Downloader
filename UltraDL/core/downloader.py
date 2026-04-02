"""
High-level single-job orchestration: extract → pick stream → download → merge.

``VideoDownloader`` is intentionally **not** threaded; the ``DownloadManager``
and ``TaskScheduler`` wrap it with queue semantics. This class contains the
deterministic state machine a developer can unit-test without the scheduler.
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..extractors import ExtractorContext, ExtractedVideo, StreamCandidate, StreamKind, get_default_registry
from ..metadata import MetadataExtractor, SubtitleExtractor, ThumbnailDownloader, UnifiedMetadata
from ..streaming.dash_parser import DASHParser
from ..streaming.segment_merger import FFmpegMerger, SegmentMerger
from ..utils.config_loader import AppConfig
from ..utils.file_utils import safe_filename
from ..utils.logger import get_logger
from ..utils.network_utils import HTTPClient
from .retry_handler import RetryHandler, RetryPolicy
from .segment_downloader import ByteRangeDownloader, SegmentDownloader

log = get_logger("downloader")


ProgressHook = Callable[[Dict[str, float]], None]


@dataclass
class DownloadResult:
    output_path: Path
    metadata_path: Optional[Path]
    extracted: ExtractedVideo


def _hash_key(url: str) -> str:
    import hashlib

    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class MetadataCache:
    """Tiny on-disk cache for ``ExtractedVideo`` payloads (serialized lightly)."""

    def __init__(self, cache_dir: Path, ttl_seconds: int) -> None:
        self.cache_dir = cache_dir
        self.ttl = ttl_seconds

    def get(self, url: str) -> Optional[ExtractedVideo]:
        path = self.cache_dir / f"{_hash_key(url)}.json"
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.ttl:
            path.unlink(missing_ok=True)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _deserialize_extracted(data)
        except Exception:
            return None

    def put(self, url: str, ev: ExtractedVideo) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{_hash_key(url)}.json"
        path.write_text(json.dumps(_serialize_extracted(ev), indent=2), encoding="utf-8")


def _serialize_extracted(ev: ExtractedVideo) -> dict:
    return {
        "canonical_url": ev.canonical_url,
        "title": ev.title,
        "description": ev.description,
        "uploader": ev.uploader,
        "upload_date": ev.upload_date,
        "thumbnail_urls": list(ev.thumbnail_urls),
        "streams": [
            {
                "kind": s.kind.name,
                "url": s.url,
                "height": s.height,
                "width": s.width,
                "bitrate": s.bitrate,
                "fps": s.fps,
                "codecs": s.codecs,
                "language": s.language,
                "is_hdr": s.is_hdr,
                "label": s.label,
            }
            for s in ev.streams
        ],
        "subtitles": [asdict(s) for s in ev.subtitles],
        "related_pages": [asdict(r) for r in ev.related_pages],
        "extractor_id": ev.extractor_id,
        "raw_debug": dict(ev.raw_debug),
    }


def _deserialize_extracted(d: dict) -> ExtractedVideo:
    from ..extractors.base_extractor import CrawlSeed, StreamCandidate, SubtitleRef

    streams = []
    for s in d.get("streams", []):
        streams.append(
            StreamCandidate(
                kind=StreamKind[s["kind"]],
                url=s["url"],
                height=s.get("height"),
                width=s.get("width"),
                bitrate=s.get("bitrate"),
                fps=s.get("fps"),
                codecs=s.get("codecs"),
                language=s.get("language"),
                is_hdr=bool(s.get("is_hdr")),
                label=s.get("label") or "",
            )
        )
    subs = [SubtitleRef(**x) for x in d.get("subtitles", [])]
    rel = [CrawlSeed(**x) for x in d.get("related_pages", [])]
    return ExtractedVideo(
        canonical_url=d["canonical_url"],
        title=d["title"],
        description=d.get("description") or "",
        uploader=d.get("uploader") or "",
        upload_date=d.get("upload_date"),
        thumbnail_urls=list(d.get("thumbnail_urls") or []),
        subtitles=subs,
        streams=streams,
        related_pages=rel,
        extractor_id=d.get("extractor_id") or "",
        raw_debug=dict(d.get("raw_debug") or {}),
    )


class VideoDownloader:
    def __init__(
        self,
        config: AppConfig,
        http: Optional[HTTPClient] = None,
        *,
        registry=None,
    ) -> None:
        self.config = config
        self.http = http or HTTPClient(config.user_agent, timeout=config.timeout_seconds)
        self.registry = registry or get_default_registry()
        self._seg = SegmentDownloader(
            self.http,
            max_workers=config.max_segment_workers,
            retry=RetryHandler(
                RetryPolicy(
                    max_attempts=config.retry_attempts,
                    base_delay=config.retry_backoff_base,
                )
            ),
        )
        self._range = ByteRangeDownloader(self.http, chunk_size=config.chunk_size_bytes)
        self._cache = MetadataCache(
            config.effective_cache_dir() / "metadata",
            config.cache_ttl_seconds,
        )

    def close(self) -> None:
        self.http.close()

    def extract(self, url: str, *, use_cache: bool = True) -> ExtractedVideo:
        if use_cache and self.config.enable_metadata_cache:
            hit = self._cache.get(url)
            if hit:
                log.info("Cache hit for %s", url)
                return hit
        ex = self.registry.pick(url)
        if not ex:
            raise RuntimeError(f"No extractor registered for URL: {url}")
        ctx = ExtractorContext(self.http, self.config)
        ev = ex.extract(url, ctx)
        if self.config.enable_metadata_cache:
            self._cache.put(url, ev)
        return ev

    def pick_stream(
        self,
        ev: ExtractedVideo,
        *,
        preferred_height: int,
        prefer_progressive: bool = True,
    ) -> StreamCandidate:
        if not ev.streams:
            raise RuntimeError("No streams discovered for this URL.")
        candidates = list(ev.streams)

        def is_prog(sc: StreamCandidate) -> bool:
            return sc.kind == StreamKind.PROGRESSIVE

        if prefer_progressive:
            candidates.sort(key=lambda s: (0 if is_prog(s) else 1, score_height(s, preferred_height)))
        else:
            candidates.sort(key=lambda s: score_height(s, preferred_height))

        # Prefer concrete resolution near target
        return candidates[0]


def score_height(s: StreamCandidate, preferred: int) -> int:
    h = s.height or 0
    delta = abs(h - preferred)
    penalty = 3000 if h > preferred else 0
    bw = -(s.bitrate or 0) // 1000
    return delta + penalty + bw


class DownloadSession:
    """One download from URL to output file with progress callbacks."""

    def __init__(self, downloader: VideoDownloader) -> None:
        self.dl = downloader
        self.stop_event = threading.Event()

    def run(
        self,
        url: str,
        output_dir: Path,
        *,
        preferred_height: Optional[int] = None,
        output_format: str = "mp4",
        write_metadata: bool = True,
        download_thumbnail: bool = True,
        download_subs: bool = True,
        subtitle_formats: Optional[set[str]] = None,
        live: bool = False,
        progress: Optional[ProgressHook] = None,
        use_cache: bool = True,
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
    ) -> DownloadResult:
        cfg = self.dl.config
        height = preferred_height or cfg.preferred_height
        cancel_event = stop_event if stop_event is not None else self.stop_event
        pause_event = pause_event
        ev = self.dl.extract(url, use_cache=use_cache)
        stream = self.dl.pick_stream(ev, preferred_height=height)
        meta = UnifiedMetadata.from_extracted(ev)
        base_name = safe_filename(meta.title)
        out_dir = output_dir / base_name
        out_dir.mkdir(parents=True, exist_ok=True)

        if download_thumbnail and ev.thumbnail_urls:
            ThumbnailDownloader(self.dl.http).download_best(ev.thumbnail_urls, out_dir / "thumbnail")

        sub_paths = []
        if download_subs and ev.subtitles:
            sub_paths = SubtitleExtractor(self.dl.http).download_tracks(
                ev.subtitles,
                out_dir,
                stem=base_name,
                allowed_formats=subtitle_formats,
            )
            meta.subtitle_paths = [str(p.path) for p in sub_paths]

        final = out_dir / f"{base_name}.{output_format}"

        start = time.monotonic()
        bytes_done = 0

        last_report = 0.0

        def bump(
            extra_bytes: int = 0,
            *,
            done: Optional[int] = None,
            total: Optional[int] = None,
        ) -> None:
            nonlocal bytes_done, last_report
            bytes_done += int(extra_bytes)
            if not progress:
                return

            elapsed = max(1e-6, time.monotonic() - start)
            pct = 0.0
            if done is not None and total is not None and total > 0:
                pct = max(0.0, min(100.0, (done / total) * 100.0))

            eta = 0.0
            if pct > 0.0:
                eta = elapsed * (1.0 - pct / 100.0) / max(pct / 100.0, 1e-6)

            now = time.monotonic()
            # Throttle updates for smooth UI
            if now - last_report < 0.05 and pct == 0.0:
                return
            last_report = now

            progress(
                {
                    "bytes": float(bytes_done),
                    "speed": float(bytes_done / elapsed),
                    "pct": float(pct),
                    "eta": float(eta),
                }
            )

        with tempfile.TemporaryDirectory(prefix="ultradl_job_") as tmp:
            tmpdir = Path(tmp)
            if stream.kind == StreamKind.HLS:
                if live:
                    parts = self.dl._seg.download_playlist_while_live(
                        stream.url,
                        tmpdir / "hls",
                        cfg.live_poll_interval,
                        cancel_event,
                        pause_event=pause_event,
                        progress=lambda d, t, b: bump(b, done=d, total=t),
                    )
                else:
                    parts = self.dl._seg.download_hls_vod(
                        stream.url,
                        tmpdir / "hls",
                        stop_event=cancel_event,
                        pause_event=pause_event,
                        progress=lambda d, t, b: bump(b, done=d, total=t),
                    )
                if cancel_event.is_set():
                    raise RuntimeError("Download cancelled")
                ffm = FFmpegMerger(cfg.ffmpeg_path)
                concat_list = tmpdir / "concat.txt"
                ffm.write_concat_list(parts, concat_list)
                intermediates = tmpdir / "merged.ts"
                ffm.concat_demuxer(concat_list, intermediates, codec_copy=True)
                ffm.remux(intermediates, final, codec_copy=True)
            elif stream.kind == StreamKind.DASH:
                text = self.dl.http.get_text(stream.url)
                man = DASHParser().parse_text(text, stream.url)
                rep = DASHParser.pick_representation_for_height(man, height)
                if rep is None:
                    raise RuntimeError("Could not pick a DASH video representation")
                if rep.content_protected:
                    raise RuntimeError("DASH content is DRM protected — cannot download")
                init_path: Optional[Path] = None
                urls = [s.url for s in rep.segments]
                parts = self.dl._seg.download_urls_ordered(
                    urls,
                    tmpdir / "dash",
                    prefix="d",
                    stop_event=cancel_event,
                    pause_event=pause_event,
                    progress=lambda d, t, b: bump(b, done=d, total=t),
                )
                ffm = FFmpegMerger(cfg.ffmpeg_path)
                concat_list = tmpdir / "dash_concat.txt"
                ffm.write_concat_list(parts, concat_list)
                dash_merged = tmpdir / "dash_merged.mp4"
                try:
                    ffm.concat_demuxer(concat_list, dash_merged, codec_copy=True)
                except Exception:
                    # Binary concat fallback when FFmpeg concat demuxer rejects fMP4 chain
                    SegmentMerger.concat_files(parts, tmpdir / "dash_raw.bin")
                    dash_merged = tmpdir / "dash_raw.bin"
                ffm.remux(dash_merged, final, codec_copy=True)
            else:
                # Progressive OR unknown — prefer ranged parallel when length known
                from ..utils.network_utils import guess_extension_from_url
                ext = guess_extension_from_url(stream.url) or ".bin"
                self.dl._range.download_parallel(
                    stream.url,
                    tmpdir / f"prog{ext}",
                    workers=min(8, cfg.max_segment_workers),
                    stop_event=cancel_event,
                    pause_event=pause_event,
                    progress=lambda d, t, b: bump(b, done=d, total=t),
                )
                if cancel_event.is_set():
                    raise RuntimeError("Download cancelled")
                FFmpegMerger(cfg.ffmpeg_path).remux(tmpdir / f"prog{ext}", final, codec_copy=True)

        meta_path: Optional[Path] = None
        if write_metadata:
            meta_path = MetadataExtractor.write_sidecar(final, meta)
        bump(0)
        return DownloadResult(output_path=final, metadata_path=meta_path, extracted=ev)
