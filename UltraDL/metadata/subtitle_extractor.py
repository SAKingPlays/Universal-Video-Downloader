"""
Subtitle fetching and light normalization.

Many providers expose WebVTT; UltraDL stores ``.vtt`` and ``.srt`` when simple
conversion is possible (WEBVTT header strip + blank-line heuristics).

Timed-text URLs that return proprietary XML are saved verbatim with a
``.xml`` extension to avoid mangling timing data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..extractors.base_extractor import SubtitleRef
from ..utils.logger import get_logger
from ..utils.network_utils import HTTPClient

log = get_logger("subtitle")


@dataclass
class SubtitleTrack:
    language: str
    path: Path
    format: str


class SubtitleExtractor:
    def __init__(self, client: HTTPClient) -> None:
        self._client = client

    def download_tracks(
        self,
        tracks: List[SubtitleRef],
        dest_dir: Path,
        stem: str,
        *,
        allowed_formats: Optional[set[str]] = None,
    ) -> List[SubtitleTrack]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        saved: List[SubtitleTrack] = []
        for idx, tr in enumerate(tracks):
            if allowed_formats is not None:
                # Treat srv3 as VTT for UX purposes
                fmt = "vtt" if tr.format == "srv3" else tr.format
                if fmt not in allowed_formats:
                    continue
            ext = ".vtt" if tr.format in {"vtt", "srv3"} else ".srt" if tr.format == "srt" else ".txt"
            path = dest_dir / f"{stem}.{tr.language}.{idx}{ext}"
            try:
                res = self._client.get_bytes(tr.url)
                if res.status_code != 200:
                    continue
                data = res.content
                if ext == ".srt" and b"WEBVTT" in data[:20].upper():
                    data = self._webvtt_to_srt(data.decode("utf-8", errors="ignore")).encode("utf-8")
                path.write_bytes(data)
                saved.append(SubtitleTrack(language=tr.language, path=path, format=tr.format))
            except Exception as exc:
                log.debug("Subtitle download failed: %s", exc)
        return saved

    @staticmethod
    def _webvtt_to_srt(webvtt: str) -> str:
        """Very small WEBVTT → SRT converter (good enough for simple captions)."""
        lines = webvtt.splitlines()
        out: List[str] = []
        idx = 1
        buffer: List[str] = []
        time_line: Optional[str] = None

        def flush() -> None:
            nonlocal idx, buffer, time_line
            if time_line and buffer:
                # VTT time uses . for ms; SRT uses ,
                t = time_line.replace(".", ",", 1)
                out.append(str(idx))
                out.append(t)
                out.extend(buffer)
                out.append("")
                idx += 1
            buffer = []
            time_line = None

        for ln in lines:
            if ln.strip().upper().startswith("WEBVTT"):
                continue
            if "-->" in ln:
                flush()
                time_line = ln.strip()
                continue
            if not ln.strip():
                continue
            buffer.append(ln.strip())
        flush()
        return "\n".join(out)
