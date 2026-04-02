"""
Segment assembly and FFmpeg integration.

UltraDL writes transport streams or fragmented MP4 parts to a temp directory,
then either byte-concatenates them (``cat`` semantics for TS) or invokes
``ffmpeg`` to remux into user-requested containers (MP4/MKV/WebM).

Why FFmpeg here? Building a full fMP4 demuxer/muxer in Python would duplicate
years of libav work. The **download and parse** paths are pure Python; **container
finalization** defers to FFmpeg when precision is required (timestamps, codec copy).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..utils.logger import get_logger

log = get_logger("merger")


class SegmentMerger:
    """Concatenate binary segments in order (suitable for MPEG-TS)."""

    @staticmethod
    def concat_files(parts: Sequence[Path], dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            for p in parts:
                with p.open("rb") as f:
                    shutil.copyfileobj(f, out)


class FFmpegMerger:
    """Invoke FFmpeg for remux, transcode (optional), and HLS/DASH finalization."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def concat_demuxer(self, list_file: Path, output: Path, *, codec_copy: bool = True) -> None:
        """
        Use FFmpeg's concat *demuxer* with a list file::

            file 'segment000.ts'
            file 'segment001.ts'

        ``list_file`` must use FFmpeg escaping rules for paths on Windows.
        """
        args = [self.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file)]
        if codec_copy:
            args += ["-c", "copy"]
        args += [str(output)]
        log.info("Running ffmpeg: %s", " ".join(args))
        subprocess.run(args, check=True, capture_output=True, text=True)

    def remux(self, input_path: Path, output_path: Path, *, codec_copy: bool = True) -> None:
        """Simple remux/transcode wrapper."""
        args = [self.ffmpeg_path, "-y", "-i", str(input_path)]
        if codec_copy:
            args += ["-c", "copy"]
        args += [str(output_path)]
        subprocess.run(args, check=True, capture_output=True, text=True)

    def write_concat_list(self, segments: Iterable[Path], list_path: Path) -> None:
        lines: List[str] = []
        for s in segments:
            # Escape single quotes for concat demuxer
            p = str(s.resolve()).replace("'", r"'\''")
            lines.append(f"file '{p}'")
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def merge_to_format(
        self,
        segment_paths: Sequence[Path],
        output: Path,
        *,
        container: str = "mp4",
        codec_copy: bool = True,
    ) -> None:
        """
        Merge ordered segments into ``output`` with extension implying container.

        For ``.ts`` inputs, concat demuxer + copy is used. For fMP4 fragments,
        callers may pre-merge to a single file and call ``remux``.
        """
        output = output.with_suffix(f".{container}")
        with tempfile.TemporaryDirectory(prefix="ultradl_ff_") as tmp:
            tmpdir = Path(tmp)
            list_path = tmpdir / "concat.txt"
            self.write_concat_list(segment_paths, list_path)
            self.concat_demuxer(list_path, output, codec_copy=codec_copy)

    @staticmethod
    def is_available(ffmpeg_path: str = "ffmpeg") -> bool:
        try:
            subprocess.run(
                [ffmpeg_path, "-version"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception:
            return False


def probe_duration_seconds(path: Path, ffprobe_path: str = "ffprobe") -> Optional[float]:
    try:
        out = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return None
