"""
Parallel segment downloader with bounded worker pools.

Segments (HLS ``.ts``, DASH ``.m4s``, byte-range chunks) are downloaded into a
temporary directory with stable ordering. The downloader:

- Uses ``ThreadPoolExecutor`` for robust blocking I/O with ``httpx``.
- Supports cooperative **cancel** via a shared ``threading.Event``.
- Retries individual segments using ``RetryHandler``.
- Reports progress through a thread-safe callback.

For **live** playlists, call ``download_playlist_while_live`` which polls the
manifest for new segments until stopped.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..streaming.hls_parser import HLSParser
from ..utils.logger import get_logger
from ..utils.network_utils import HTTPClient
from .retry_handler import RetryHandler, RetryPolicy

log = get_logger("segment_dl")

ProgressCallback = Callable[[int, int, int], None]  # done_count, total, bytes_this_tick


class SegmentDownloader:
    def __init__(
        self,
        http: HTTPClient,
        *,
        max_workers: int = 8,
        retry: Optional[RetryHandler] = None,
    ) -> None:
        self._http = http
        self._max_workers = max_workers
        self._retry = retry or RetryHandler(RetryPolicy())

    def download_urls_ordered(
        self,
        urls: List[str],
        out_dir: Path,
        *,
        prefix: str = "seg",
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
        progress: Optional[ProgressCallback] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> List[Path]:
        """
        Download ``urls`` in parallel but return **ordered** local paths.

        Filenames are zero-padded so lexicographic order == playlist order.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        width = max(5, len(str(len(urls))))
        planned: List[Tuple[int, str, Path]] = []
        for i, u in enumerate(urls):
            planned.append((i, u, out_dir / f"{prefix}_{i:0{width}d}.bin"))

        done = 0
        total = len(planned)
        lock = threading.Lock()

        def job(idx: int, url: str, path: Path) -> Tuple[int, Path]:
            nonlocal done
            if stop_event and stop_event.is_set():
                raise RuntimeError("cancelled")

            if pause_event is not None:
                while not pause_event.is_set():
                    if stop_event and stop_event.is_set():
                        raise RuntimeError("cancelled")
                    time.sleep(0.2)

            def once() -> None:
                headers = dict(extra_headers or {})
                res = self._http.get_bytes(url, headers=headers)
                if res.status_code >= 400:
                    raise RuntimeError(f"HTTP {res.status_code} for segment {url[:120]}")
                path.write_bytes(res.content)

            self._retry.run(once)
            with lock:
                done += 1
                if progress:
                    progress(done, total, path.stat().st_size)
            return idx, path

        results: Dict[int, Path] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            futs: List[Future[Tuple[int, Path]]] = []
            for idx, url, path in planned:
                futs.append(ex.submit(job, idx, url, path))
            for fut in as_completed(futs):
                idx, path = fut.result()
                results[idx] = path
        return [results[i] for i in range(len(urls))]

    def download_hls_vod(
        self,
        manifest_url: str,
        out_dir: Path,
        *,
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> List[Path]:
        text = self._http.get_text(manifest_url)
        parser = HLSParser()
        master, media = parser.parse(text, manifest_url)
        if master:
            variant = HLSParser.pick_variant_for_height(master, 1080) or (
                master.variants[0] if master.variants else None
            )
            if not variant:
                raise RuntimeError("Empty HLS master playlist")
            text = self._http.get_text(variant.uri)
            _, media = parser.parse(text, variant.uri)
        if not media:
            raise RuntimeError("Could not parse HLS media playlist")
        if media.is_encrypted:
            raise RuntimeError(
                f"HLS encryption ({media.encryption_method}) is not supported in UltraDL yet."
            )
        urls = [s.uri for s in media.segments]
        return self.download_urls_ordered(
            urls,
            out_dir,
            prefix="hls",
            stop_event=stop_event,
            pause_event=pause_event,
            progress=progress,
        )

    def download_playlist_while_live(
        self,
        manifest_url: str,
        out_dir: Path,
        poll_interval: float,
        stop_event: threading.Event,
        pause_event: Optional[threading.Event] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> List[Path]:
        """
        Poll an HLS media playlist for new segments until ``stop_event`` is set.

        Discovered segments are written as ``live_00001.bin`` in playlist order.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        parser = HLSParser()
        seen_set: set[str] = set()
        file_counter = 0
        width = 8

        while not stop_event.is_set():
            if pause_event is not None and not pause_event.is_set():
                time.sleep(0.2)
                continue
            text = self._http.get_text(manifest_url)
            _, media = parser.parse(text, manifest_url)
            if not media:
                time.sleep(poll_interval)
                continue
            batch_urls: List[str] = []
            for s in media.segments:
                if s.uri in seen_set:
                    continue
                seen_set.add(s.uri)
                batch_urls.append(s.uri)
            if batch_urls:
                planned = list(
                    enumerate(batch_urls, start=file_counter),
                )
                file_counter += len(batch_urls)

                def job(pair: Tuple[int, str]) -> Path:
                    i, u = pair
                    path = out_dir / f"live_{i:0{width}d}.bin"
                    if stop_event.is_set():
                        raise RuntimeError("cancelled")

                    if pause_event is not None:
                        while not pause_event.is_set():
                            if stop_event.is_set():
                                raise RuntimeError("cancelled")
                            time.sleep(0.2)

                    def once() -> None:
                        res = self._http.get_bytes(u)
                        if res.status_code >= 400:
                            raise RuntimeError(f"HTTP {res.status_code}")
                        path.write_bytes(res.content)

                    self._retry.run(once)
                    if progress:
                        progress(i + 1, file_counter, path.stat().st_size)
                    return path

                with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
                    futs = [ex.submit(job, p) for p in planned]
                    for fut in as_completed(futs):
                        fut.result()

            if media.endlist:
                break
            time.sleep(poll_interval)

        return sorted(out_dir.glob("live_*.bin"))


class ByteRangeDownloader:
    """Download a large progressive file in parallel HTTP Range chunks."""

    def __init__(self, http: HTTPClient, chunk_size: int = 4 * 1024 * 1024) -> None:
        self._http = http
        self._chunk_size = chunk_size

    def probe_length(self, url: str) -> Optional[int]:
        try:
            r = self._http.head(url, follow_redirects=True)
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit():
                return int(cl)
        except Exception:
            return None
        return None

    def download_parallel(
        self,
        url: str,
        dest: Path,
        *,
        workers: int = 6,
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
        progress: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        """
        If the server supports ranges, download in parallel parts; else fallback single GET.
        """
        length = self.probe_length(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")

        if not length or length < self._chunk_size * 2:
            if pause_event is not None:
                while not pause_event.is_set():
                    if stop_event and stop_event.is_set():
                        raise RuntimeError("cancelled")
                    time.sleep(0.2)
            self._http.download_to_path(url, dest, resume=True)
            return

        ranges: List[Tuple[int, int]] = []
        start = 0
        while start < length:
            end = min(start + self._chunk_size - 1, length - 1)
            ranges.append((start, end))
            start = end + 1

        def fetch_range(span: Tuple[int, int]) -> Tuple[int, bytes]:
            if stop_event and stop_event.is_set():
                raise RuntimeError("cancelled")
            if pause_event is not None:
                while not pause_event.is_set():
                    if stop_event and stop_event.is_set():
                        raise RuntimeError("cancelled")
                    time.sleep(0.2)
            a, b = span
            headers = {"Range": f"bytes={a}-{b}"}
            res = self._http.get_bytes(url, headers=headers)
            if res.status_code not in (206, 200):
                raise RuntimeError(f"Bad range response {res.status_code}")
            return a, res.content

        parts: Dict[int, bytes] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(fetch_range, span) for span in ranges]
            done = 0
            for fut in as_completed(futs):
                a, data = fut.result()
                parts[a] = data
                done += 1
                if progress:
                    progress(done, len(ranges), len(data))

        with part.open("wb") as f:
            for a, _ in sorted(parts.keys()):
                f.write(parts[a])
        part.replace(dest)
