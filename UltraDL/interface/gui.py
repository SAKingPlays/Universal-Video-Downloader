"""
Minimal Tkinter GUI for interactive downloads.

The GUI intentionally stays small: paste URL, pick output folder and quality,
then start. Heavy lifting remains in ``VideoDownloader`` so automation and
GUI share identical semantics.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from ..core.downloader import DownloadSession, VideoDownloader
from ..utils.config_loader import AppConfig, load_config


def launch_gui() -> None:
    root = tk.Tk()
    root.title("UltraDL")
    cfg = load_config()

    frm = ttk.Frame(root, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    ttk.Label(frm, text="URL").grid(row=0, column=0, sticky="w")
    url_var = tk.StringVar()
    ttk.Entry(frm, textvariable=url_var, width=72).grid(row=1, column=0, columnspan=3, sticky="ew")

    ttk.Label(frm, text="Output folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
    out_var = tk.StringVar(value=str(cfg.download_dir))
    out_entry = ttk.Entry(frm, textvariable=out_var, width=60)
    out_entry.grid(row=3, column=0, columnspan=2, sticky="ew")

    def browse() -> None:
        p = filedialog.askdirectory()
        if p:
            out_var.set(p)

    ttk.Button(frm, text="Browse…", command=browse).grid(row=3, column=2, sticky="e")

    ttk.Label(frm, text="Preferred height (e.g. 1080)").grid(row=4, column=0, sticky="w", pady=(8, 0))
    q_var = tk.StringVar(value=str(cfg.preferred_height))
    ttk.Entry(frm, textvariable=q_var, width=10).grid(row=4, column=1, sticky="w")

    ttk.Label(frm, text="Container").grid(row=5, column=0, sticky="w", pady=(8, 0))
    fmt_var = tk.StringVar(value="mp4")
    ttk.Combobox(frm, textvariable=fmt_var, values=("mp4", "mkv", "webm"), width=8).grid(
        row=5, column=1, sticky="w"
    )

    live_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Live HLS (keep recording until stopped)", variable=live_var).grid(
        row=6, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )

    log_box = scrolledtext.ScrolledText(frm, height=18, state="disabled", font=("Consolas", 9))
    log_box.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
    frm.rowconfigure(8, weight=1)
    frm.columnconfigure(0, weight=1)

    def log_line(msg: str) -> None:
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def ui_log(msg: str) -> None:
        root.after(0, lambda m=msg: log_line(m))

    stop_event = threading.Event()

    def run_download() -> None:
        u = url_var.get().strip()
        if not u:
            messagebox.showwarning("UltraDL", "Enter a URL")
            return
        try:
            height = int(q_var.get())
        except ValueError:
            messagebox.showwarning("UltraDL", "Quality must be an integer")
            return
        out = Path(out_var.get())
        local_cfg = AppConfig(
            download_dir=out,
            preferred_height=height,
            max_concurrent_downloads=cfg.max_concurrent_downloads,
            max_segment_workers=cfg.max_segment_workers,
            user_agent=cfg.user_agent,
            ffmpeg_path=cfg.ffmpeg_path,
        )
        stop_event.clear()

        def worker() -> None:
            ui_log("Starting…")
            dl = VideoDownloader(local_cfg)
            session = DownloadSession(dl)
            try:
                session.run(
                    u,
                    out,
                    preferred_height=height,
                    output_format=fmt_var.get(),
                    live=live_var.get(),
                    progress=lambda m: ui_log(f"speed={m.get('speed',0)/1024/1024:.2f} MiB/s"),
                    stop_event=stop_event,
                )
                ui_log("Done.")
            except Exception as exc:
                ui_log(f"ERROR: {exc}")
            finally:
                dl.close()

        threading.Thread(target=worker, daemon=True).start()

    def stop_download() -> None:
        stop_event.set()
        log_line("Stop requested…")

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
    ttk.Button(btn_row, text="Download", command=run_download).pack(side="left", padx=(0, 8))
    ttk.Button(btn_row, text="Stop", command=stop_download).pack(side="left")

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
