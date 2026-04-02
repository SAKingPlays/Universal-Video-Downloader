"""
Command-line interface built on ``argparse`` with optional Rich progress.

The CLI is the primary operator surface for headless servers. It translates
flags into ``AppConfig`` mutations, wires logging, and runs either a single
synchronous download or a managed queue session.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from ..core.download_manager import DownloadManager
from ..core.downloader import DownloadSession, VideoDownloader
from ..utils.config_loader import load_config, save_example_config
from ..utils.logger import get_logger, setup_logging
from ..streaming.segment_merger import FFmpegMerger

log = get_logger("cli")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ultradl",
        description="UltraDL - universal modular video downloader",
    )
    p.add_argument("url", nargs="?", help="Video or playlist URL")
    p.add_argument("-o", "--output", type=Path, help="Output directory")
    p.add_argument("-q", "--quality", type=int, default=None, help="Preferred height (e.g. 720)")
    p.add_argument(
        "-f",
        "--format",
        default="mp4",
        choices=["mp4", "mkv", "webm"],
        help="Container format",
    )
    p.add_argument("--live", action="store_true", help="Treat HLS as a live sliding window")
    p.add_argument("--playlist", action="store_true", help="Expand playlist/channel links from seed URL")
    p.add_argument("--max", type=int, default=50, help="Max URLs when using --playlist")
    p.add_argument("--config", type=Path, help="Path to YAML/JSON config")
    p.add_argument("--dump-example-config", type=Path, help="Write example JSON config and exit")
    p.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Rotating log file (default: only stderr unless set)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    p.add_argument("--queue", action="store_true", help="Enqueue on background workers instead of foreground")
    p.add_argument("--gui", action="store_true", help="Launch modern UltraDL Qt GUI")
    p.add_argument("--check-ffmpeg", action="store_true", help="Verify ffmpeg is on PATH and exit")
    p.add_argument(
        "--list-formats",
        action="store_true",
        help="Resolve the URL and print discovered streams, then exit",
    )
    return p


def run_cli(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.dump_example_config:
        save_example_config(args.dump_example_config)
        print(f"Wrote example config to {args.dump_example_config}")
        return 0

    if args.check_ffmpeg:
        ok = FFmpegMerger.is_available()
        print("ffmpeg: OK" if ok else "ffmpeg: NOT FOUND")
        return 0 if ok else 2

    if args.gui:
        try:
            from .modern_gui import launch_modern_gui
            launch_modern_gui()
        except ImportError as e:
            print(
                f"PySide6 is not installed or GUI failed to load: {e}\n"
                "Install dependencies with `pip install -r requirements.txt`.",
                file=sys.stderr,
            )
            return 2
        return 0

    cfg = load_config(args.config)
    if args.output:
        cfg.download_dir = args.output
    if args.quality:
        cfg.preferred_height = args.quality

    setup_logging(
        logging.DEBUG if args.verbose else logging.INFO,
        log_file=args.log_file,
    )

    if not args.url:
        print("error: URL required unless using --gui or --dump-example-config", file=sys.stderr)
        return 2

    if args.list_formats:
        dl = VideoDownloader(cfg)
        try:
            ev = dl.extract(args.url, use_cache=True)
        finally:
            dl.close()
        print(f"Title : {ev.title}")
        print(f"Source: {ev.canonical_url}")
        print(f"Extractor: {ev.extractor_id}")
        print("Streams:")
        for i, s in enumerate(ev.streams, 1):
            tier = s.quality_tier()
            kind = s.kind.name
            dim = ""
            if s.width and s.height:
                dim = f"{s.width}x{s.height}"
            br = f"{s.bitrate // 1000} kbps" if s.bitrate else ""
            print(f"  {i:>3}. [{kind:<11}] {tier:<8} {dim:<12} {br:<12} {s.label}")
            print(f"       {s.url[:120]}{'...' if len(s.url) > 120 else ''}")
        if ev.subtitles:
            print("Subtitles:")
            for t in ev.subtitles:
                print(f"  - {t.language} ({t.format}) {t.url[:100]}")
        return 0

    if args.playlist:
        mgr = DownloadManager(cfg)
        try:
            urls = mgr.expand_playlist_or_channel(args.url, max_urls=args.max)
            print(f"Discovered {len(urls)} URLs")
            if args.queue:
                mgr.start_scheduler()
                for u in urls:
                    mgr.enqueue_url(u, output_format=args.format, live=args.live)
                print("Queued. Press Ctrl+C to exit (downloads continue in workers until process ends).")
                import time

                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                dl = mgr.downloader
                session = DownloadSession(dl)
                for i, u in enumerate(urls, 1):
                    print(f"[{i}/{len(urls)}] {u}")
                    try:
                        if _rich_available():
                            _run_with_rich(session, u, cfg.download_dir, args.format, args.live, cfg.preferred_height)
                        else:
                            session.run(
                                u,
                                cfg.download_dir,
                                preferred_height=cfg.preferred_height,
                                output_format=args.format,
                                live=args.live,
                            )
                    except Exception as exc:
                        log.error("Failed %s: %s", u, exc)
        finally:
            mgr.close()
        return 0

    if args.queue:
        mgr = DownloadManager(cfg)
        try:
            mgr.start_scheduler()
            mgr.enqueue_url(args.url, output_format=args.format, live=args.live)
            print("Queued one task. Ctrl+C to exit.")
            import time

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        finally:
            mgr.close()
        return 0

    try:
        dl = VideoDownloader(cfg)
        try:
            session = DownloadSession(dl)
            if _rich_available():
                _run_with_rich(
                    session,
                    args.url,
                    cfg.download_dir,
                    args.format,
                    args.live,
                    cfg.preferred_height,
                )
            else:
                session.run(
                    args.url,
                    cfg.download_dir,
                    preferred_height=cfg.preferred_height,
                    output_format=args.format,
                    live=args.live,
                )
            return 0
        finally:
            dl.close()
    except Exception as exc:
        log.exception("Download failed: %s", exc)
        return 1


def _rich_available() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _run_with_rich(
    session: DownloadSession,
    url: str,
    out: Path,
    fmt: str,
    live: bool,
    height: int,
) -> None:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task_id = progress.add_task("downloading", total=None)

        def hook(meta: dict) -> None:
            spd = meta.get("speed", 0.0) / (1024 * 1024)
            progress.update(task_id, description=f"{spd:.2f} MiB/s")

        session.run(
            url,
            out,
            preferred_height=height,
            output_format=fmt,
            live=live,
            progress=lambda m: hook(m),
        )


if __name__ == "__main__":
    raise SystemExit(run_cli())
