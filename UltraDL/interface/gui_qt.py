from __future__ import annotations

"""
Premium UltraDL Qt UI (PySide6).

Goals
-----
1. Modern, premium visuals (dark mode, glassmorphism, gradients, shadows).
2. Responsive UX: extraction + downloads run in background workers.
3. Real-time feedback: animated progress rings/waves, speed + ETA.
4. Per-download controls: pause/resume/cancel (cooperative).

Limitations (engineering)
--------------------------
UltraDL's core engine is designed around cooperative pause/cancel events,
but pausing cannot interrupt an in-flight HTTP segment download mid-transfer.
The UI reflects this best-effort behavior.
"""

import json
import math
import time
import traceback
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.downloader import DownloadSession, VideoDownloader
from ..utils.config_loader import AppConfig, default_config_path, load_config
from ..utils.logger import get_logger
from ..utils.network_utils import guess_extension_from_url
from ..utils.file_utils import safe_filename
from ..extractors.base_extractor import StreamKind

log = get_logger("gui.qt")


try:
    from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTimer, Signal, QSize, QRect
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QLinearGradient, QAction
    from PySide6.QtCore import QAbstractAnimation
    from PySide6.QtCore import QEasingCurve
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    from PySide6.QtCore import QPropertyAnimation
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFrame,
        QFileDialog,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QStackedWidget,
        QStyle,
        QVBoxLayout,
        QWidget,
        QTextEdit,
        QProgressBar,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError("PySide6 is required for UltraDL Qt GUI.") from exc


APP_NAME = "UltraDL"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _tier_for_height(height: Optional[int]) -> str:
    if not height:
        return "Auto"
    h = int(height)
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
    return f"{h}p"


class GlassFrame(QFrame):
    def __init__(self, *, radius: int = 16, accent: QColor | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._radius = radius
        self._accent = accent or QColor(120, 170, 255, 255)
        self.setObjectName("glassFrame")
        self._apply_style()

    def _apply_style(self) -> None:
        # Pure QSS for lightweight visuals
        r = self._radius
        a = self._accent.name()
        self.setStyleSheet(
            f"""
            GlassFrame#glassFrame {{
                background-color: rgba(24, 26, 38, 160);
                border: 1px solid rgba(255,255,255, 22);
                border-radius: {r}px;
                padding: 0px;
            }}
            """
        )


class ToastWidget(QWidget):
    def __init__(self, message: str, kind: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.kind = kind
        self._label = QLabel(message)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: rgba(255,255,255,220);")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(self._label)
        self.setFixedHeight(44)
        self.setStyleSheet(
            """
            background-color: rgba(20, 22, 32, 205);
            border: 1px solid rgba(255,255,255, 18);
            border-radius: 14px;
            """
        )


class ToastManager(QWidget):
    """
    Lightweight toast stack. Uses a vertical layout and QTimer-based fadeout.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self._stack: list[ToastWidget] = []

    def push(self, message: str, kind: str = "info", *, ttl_ms: int = 3500) -> None:
        toast = ToastWidget(message, kind=kind, parent=self)
        # Insert above the stretch
        self._layout.insertWidget(self._layout.count() - 1, toast)
        self._stack.append(toast)
        toast.show()

        timer = QTimer(toast)
        timer.setSingleShot(True)

        def _expire() -> None:
            if toast in self._stack:
                self._stack.remove(toast)

            effect = QGraphicsOpacityEffect(toast)
            toast.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", toast)
            anim.setDuration(420)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _cleanup() -> None:
                toast.deleteLater()
                self._layout.update()

            anim.finished.connect(_cleanup)
            anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        timer.timeout.connect(_expire)
        timer.start(ttl_ms)


class WaveRingWidget(QWidget):
    """
    Animated circular progress ring with a soft wave sweep.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pct = 0.0
        self._speed_mbps = 0.0
        self._phase = 0.0
        self.setMinimumSize(QSize(84, 84))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(32)

    def set_progress(self, pct: float, speed_bytes_per_s: float = 0.0) -> None:
        self._pct = _clamp(float(pct), 0.0, 100.0)
        self._speed_mbps = max(0.0, speed_bytes_per_s / (1024 * 1024))

    def _tick(self) -> None:
        self._phase += 0.07
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        r = min(w, h) * 0.37

        # Background ring
        bg_pen = QPen(QColor(255, 255, 255, 25), 8)
        p.setPen(bg_pen)
        p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))

        # Progress arc
        arc_span = int(360 * (self._pct / 100.0))
        gradient = QLinearGradient(int(cx - r), int(cy - r), int(cx + r), int(cy + r))
        gradient.setColorAt(0.0, QColor(110, 170, 255, 255))
        gradient.setColorAt(1.0, QColor(155, 110, 255, 255))
        prog_pen = QPen(gradient, 8)
        p.setPen(prog_pen)

        # Qt uses 1/16 degrees, and start at 3 o'clock, positive is CCW.
        p.drawArc(QRect(int(cx - r), int(cy - r), int(2 * r), int(2 * r)), -90 * 16, -arc_span * 16)

        # Wave highlight points (subtle)
        wave_color = QColor(255, 255, 255, 50)
        for i in range(0, 6):
            angle = -90 + (i * 360 / 6)
            rad = math.radians(angle + self._phase * 20.0 * (0.4 + self._pct / 100.0))
            rr = r * (0.92 + 0.05 * math.sin(self._phase + i))
            x = cx + math.cos(rad) * rr
            y = cy + math.sin(rad) * rr
            p.setPen(QPen(wave_color, 2))
            p.drawPoint(int(x), int(y))

        # Center text
        p.setPen(QColor(240, 244, 255, 230))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        p.setFont(font)
        pct_text = "—" if self._pct <= 0.0 else f"{int(self._pct)}%"
        p.drawText(int(cx) - 18, int(cy) + 4, pct_text)


class SpeedGraphWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *, max_points: int = 60):
        super().__init__(parent)
        self._max_points = max_points
        self._points: list[float] = []
        self.setMinimumHeight(52)

    def add_point(self, mbps: float) -> None:
        self._points.append(float(max(0.0, mbps)))
        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points :]
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()
        p.fillRect(0, 0, w, h, QColor(255, 255, 255, 0))

        # Border
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 10, 10)

        if len(self._points) < 2:
            return

        max_y = max(self._points) or 1.0
        max_y = max(max_y, 1.0)
        step = w / max(1, (self._max_points - 1))
        pen = QPen(QColor(110, 170, 255, 230), 2)
        p.setPen(pen)

        # Draw line graph
        pts = []
        start_x = w - step * (len(self._points) - 1)
        for i, val in enumerate(self._points):
            x = start_x + i * step
            y = h - (val / max_y) * (h - 18) - 9
            pts.append((x, y))

        for i in range(1, len(pts)):
            x1, y1 = pts[i - 1]
            x2, y2 = pts[i]
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Soft fill under curve
        # (Keep it lightweight: omit fill polygon to avoid heavy path conversions.)


class DownloadCardWidget(GlassFrame):
    """
    Animated download card with thumbnail, ring progress, speed graph, and controls.
    """

    def __init__(self, title: str, thumb: QPixmap | None = None, parent: QWidget | None = None):
        super().__init__(radius=18, parent=parent)
        self._title = title
        self._thumb = thumb
        self.job_state = "pending"

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(92, 52)
        self._thumb_label.setStyleSheet("background-color: rgba(255,255,255, 10); border-radius: 12px;")
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumb is not None and not thumb.isNull():
            self._thumb_label.setPixmap(thumb.scaled(92, 52, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self._thumb_label.setContentsMargins(0, 0, 0, 0)

        self.ring = WaveRingWidget()
        self.speed_graph = SpeedGraphWidget()

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: rgba(255,255,255,235); font-weight: 700;")

        self.meta_label = QLabel("Queued…")
        self.meta_label.setStyleSheet("color: rgba(255,255,255,160);")

        self.speed_label = QLabel("— MiB/s")
        self.speed_label.setStyleSheet("color: rgba(180, 230, 255, 220); font-weight: 700;")
        self.eta_label = QLabel("ETA: —")
        self.eta_label.setStyleSheet("color: rgba(255,255,255,160);")

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.setStyleSheet(self._btn_style(accent="rgba(255,255,255,40)"))
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(self._btn_style(accent="rgba(255,90,90,60)"))

        self.pause_btn.clicked.connect(self._toggle_pause)
        self.cancel_btn.clicked.connect(self._cancel)

        right = QVBoxLayout()
        right.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.speed_graph)

        btns = QHBoxLayout()
        btns.addWidget(self.pause_btn)
        btns.addWidget(self.cancel_btn)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)
        layout.addWidget(self._thumb_label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        center = QVBoxLayout()
        center.addWidget(self.title_label)
        center.addWidget(self.meta_label)
        center.addWidget(self.speed_label)
        center.addWidget(self.eta_label)
        center.addStretch(1)
        center.addLayout(btns)

        layout.addLayout(center, stretch=1)
        layout.addLayout(right, stretch=0)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(150)

    @staticmethod
    def _btn_style(accent: str) -> str:
        return (
            "QPushButton {"
            "color: rgba(255,255,255,235);"
            "background-color: rgba(255,255,255, 10);"
            f"border: 1px solid {accent};"
            "border-radius: 12px;"
            "padding: 8px 14px;"
            "font-weight: 650;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(255,255,255, 16);"
            "}"
        )

    def _toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.setText("Resume")
            self.meta_label.setText("Paused")
        else:
            self.pause_event.set()
            self.pause_btn.setText("Pause")
            self.meta_label.setText("Downloading…")

    def _cancel(self) -> None:
        self.stop_event.set()
        self.meta_label.setText("Cancelling…")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

    def set_status(self, text: str, *, ok: bool | None = None) -> None:
        if ok is None:
            self.meta_label.setText(text)
            return
        if ok:
            self.meta_label.setText(text)
            self.meta_label.setStyleSheet("color: rgba(120, 255, 170, 200);")
        else:
            self.meta_label.setText(text)
            self.meta_label.setStyleSheet("color: rgba(255, 120, 120, 200);")

    def update_progress(self, meta: dict[str, Any]) -> None:
        speed_b = float(meta.get("speed", 0.0))
        speed_m = speed_b / (1024 * 1024)
        pct = float(meta.get("pct", 0.0))
        eta = float(meta.get("eta", 0.0))

        self.ring.set_progress(pct, speed_b)
        self.speed_graph.add_point(speed_m)
        self.speed_label.setText(f"{speed_m:.2f} MiB/s")
        if pct > 0.0 and eta > 0.0:
            self.eta_label.setText(f"ETA: {int(eta)}s")
        else:
            self.eta_label.setText("ETA: —")


class ExtractWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    meta = Signal(str)


class ExtractWorker(QRunnable):
    def __init__(self, downloader: VideoDownloader, url: str):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.signals = ExtractWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: N802
        try:
            ev = self.downloader.extract(self.url, use_cache=True)
            self.signals.finished.emit(ev)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class PlaylistThumbSignals(QObject):
    finished = Signal(str, dict)  # url, payload
    failed = Signal(str, str)  # url, error


class PlaylistThumbWorker(QRunnable):
    """
    Best-effort: extract metadata for a playlist seed and fetch its first thumbnail.
    """

    def __init__(self, downloader: VideoDownloader, url: str):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.signals = PlaylistThumbSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: N802
        try:
            ev = self.downloader.extract(self.url, use_cache=True)
            title = str(getattr(ev, "title", "") or "")
            thumb_bytes: Optional[bytes] = None
            thumbs = getattr(ev, "thumbnail_urls", []) or []
            if thumbs:
                first = thumbs[0]
                try:
                    res = self.downloader.http.get_bytes(first)
                    if res.status_code == 200 and res.content:
                        thumb_bytes = res.content
                except Exception:
                    thumb_bytes = None
            payload = {"title": title, "thumb_bytes": thumb_bytes}
            self.signals.finished.emit(self.url, payload)
        except Exception as exc:
            self.signals.failed.emit(self.url, str(exc))


class DownloadWorkerSignals(QObject):
    progress = Signal(dict)
    finished = Signal(object)
    failed = Signal(str)
    started = Signal(str)


class DownloadWorker(QRunnable):
    def __init__(
        self,
        downloader: VideoDownloader,
        url: str,
        *,
        output_dir: Path,
        preferred_height: Optional[int],
        output_format: str,
        live: bool,
        download_thumbnail: bool,
        download_subs: bool,
        subtitle_formats: Optional[set[str]],
        stop_event: threading.Event,
        pause_event: threading.Event,
    ):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.preferred_height = preferred_height
        self.output_format = output_format
        self.live = live
        self.download_thumbnail = download_thumbnail
        self.download_subs = download_subs
        self.subtitle_formats = subtitle_formats
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.signals = DownloadWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: N802
        try:
            self.signals.started.emit(self.url)
            session = DownloadSession(self.downloader)
            res = session.run(
                self.url,
                self.output_dir,
                preferred_height=self.preferred_height,
                output_format=self.output_format,
                write_metadata=True,
                download_thumbnail=self.download_thumbnail,
                download_subs=self.download_subs,
                subtitle_formats=self.subtitle_formats,
                live=self.live,
                progress=lambda meta: self.signals.progress.emit(meta),
                stop_event=self.stop_event,
                pause_event=self.pause_event,
            )
            self.signals.finished.emit(res)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class UrlCard(GlassFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(radius=18, parent=parent)
        self.setFixedHeight(180)

        self.url_edit = QTextEdit()
        self.url_edit.setPlaceholderText("Paste a video, playlist, channel, or live stream URL…")
        self.url_edit.setStyleSheet(
            """
            QTextEdit {
                color: rgba(255,255,255,235);
                background-color: rgba(255,255,255, 10);
                border: 1px solid rgba(255,255,255, 18);
                border-radius: 16px;
                padding: 14px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid rgba(120,170,255, 55);
                background-color: rgba(120,170,255, 10);
            }
            """
        )

        self.analyze_btn = QPushButton("Analyze & Preview")
        self.analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_btn.setStyleSheet(
            """
            QPushButton {
                color: rgba(255,255,255,240);
                background: linear-gradient(135deg, rgba(80,140,255,220), rgba(160,90,255,200));
                border: 1px solid rgba(255,255,255, 14);
                border-radius: 16px;
                padding: 12px 18px;
                font-weight: 800;
            }
            QPushButton:hover {
                filter: brightness(1.06);
            }
            """
        )

        self.platform_label = QLabel("Detected: —")
        self.platform_label.setStyleSheet("color: rgba(255,255,255,175); font-weight: 650;")

        self.title_label = QLabel("Title: —")
        self.title_label.setStyleSheet("color: rgba(255,255,255,235); font-weight: 800; font-size: 14px;")

        self.subtitle_label = QLabel("Uploader: —")
        self.subtitle_label.setStyleSheet("color: rgba(255,255,255,150);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.url_edit)

        row = QHBoxLayout()
        row.addWidget(self.analyze_btn)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(self.platform_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def url_text(self) -> str:
        return self.url_edit.toPlainText().strip()

    def set_preview(self, platform: str, title: str, uploader: str) -> None:
        self.platform_label.setText(f"Detected: {platform}")
        self.title_label.setText(f"Title: {title}")
        self.subtitle_label.setText(f"Uploader: {uploader or '—'}")


class QualitySelector(GlassFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(radius=18, parent=parent)
        self.setFixedHeight(118)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "webm"])
        self.format_combo.setStyleSheet(self._combo_style())

        self.live_check = QCheckBox("Live recording (HLS)");
        self.live_check.setStyleSheet("QCheckBox { color: rgba(255,255,255,220); font-weight: 700; }")

        self.height_combo = QComboBox()
        self.height_combo.addItems(["Auto", "144p", "360p", "720p", "1080p", "4K"])
        self.height_combo.setStyleSheet(self._combo_style())

        self._map = {"Auto": None, "144p": 144, "360p": 360, "720p": 720, "1080p": 1080, "4K": 2160}

        self.chips_box = QHBoxLayout()
        self.chips_box.setSpacing(8)
        self.chips_box.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Quality & Output")
        title.setStyleSheet("color: rgba(255,255,255,235); font-weight: 850;")

        row = QHBoxLayout()
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(QLabel("Resolution"))
        row.addWidget(self.height_combo)
        row.addWidget(QLabel("Container"))
        row.addWidget(self.format_combo)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addLayout(row)
        layout.addLayout(self.chips_box)
        layout.addWidget(self.live_check)

    @staticmethod
    def _combo_style() -> str:
        return (
            """
            QComboBox {
                color: rgba(255,255,255,235);
                background-color: rgba(255,255,255, 10);
                border: 1px solid rgba(255,255,255, 18);
                border-radius: 14px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QComboBox:hover { background-color: rgba(255,255,255, 14); }
            QComboBox::drop-down { border: 0px; }
            """
        )

    def set_stream_options(self, heights: list[int]) -> None:
        # Build chip-like buttons from available heights (deduped).
        while self.chips_box.count():
            item = self.chips_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        unique = sorted(set(heights))
        for h in unique:
            btn = QPushButton(_tier_for_height(h))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                """
                QPushButton {
                    color: rgba(255,255,255,235);
                    background-color: rgba(255,255,255, 10);
                    border: 1px solid rgba(255,255,255, 18);
                    border-radius: 14px;
                    padding: 10px 12px;
                    font-weight: 850;
                }
                QPushButton:checked {
                    border: 1px solid rgba(120,170,255, 60);
                    background-color: rgba(120,170,255, 18);
                }
                QPushButton:hover { background-color: rgba(255,255,255, 14); }
                """
            )

            def _make_setter(height: int):
                return lambda checked: self._select_height_from_chip(height, checked)

            btn.clicked.connect(_make_setter(h))
            self.chips_box.addWidget(btn)

        # If user hasn't picked a tier, keep defaults.

    def _select_height_from_chip(self, height: int, checked: bool) -> None:
        if checked:
            # Map to nearest option in combo
            mapping = {144: 0, 360: 1, 720: 2, 1080: 3, 2160: 5}
            idx = mapping.get(height)
            if idx is None:
                # Insert on demand
                label = _tier_for_height(height)
                if self.height_combo.findText(label) == -1:
                    self.height_combo.addItem(label, height)
                self.height_combo.setCurrentText(label)
            else:
                self.height_combo.setCurrentIndex(idx)

    def selected_height(self) -> Optional[int]:
        # If the combo holds custom heights (chip insertion), prefer that data.
        data = self.height_combo.currentData()
        if data is not None:
            return int(data)
        label = self.height_combo.currentText()
        return self._map.get(label)

    def output_format(self) -> str:
        return str(self.format_combo.currentText()).strip()

    def live_enabled(self) -> bool:
        return bool(self.live_check.isChecked())


@dataclass
class PlaylistItem:
    url: str
    title: str = ""
    thumb: QPixmap | None = None


class PlaylistGrid(GlassFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(radius=18, parent=parent)
        self.setFixedHeight(260)
        self._items: list[tuple[QCheckBox, QLabel, PlaylistItem]] = []

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self._grid.setSpacing(12)
        self._scroll.setWidget(self._content)

        title = QLabel("Playlist (select items)")
        title.setStyleSheet("color: rgba(255,255,255,235); font-weight: 900;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(title)
        layout.addWidget(self._scroll)

    def set_items(self, items: list[PlaylistItem]) -> None:
        # Clear old
        for cb, thumb, item in self._items:
            cb.deleteLater()
            thumb.deleteLater()
        self._items.clear()

        max_cols = 3
        for i, it in enumerate(items):
            cell = QFrame()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)

            thumb = QLabel()
            thumb.setFixedSize(140, 60)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(
                "background-color: rgba(255,255,255, 10); border: 1px solid rgba(255,255,255, 18); border-radius: 14px;"
            )
            if it.thumb is not None and not it.thumb.isNull():
                thumb.setPixmap(
                    it.thumb.scaled(
                        140,
                        60,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                thumb.setText("Preview")
                thumb.setStyleSheet(
                    "background-color: rgba(120,170,255, 8); border: 1px solid rgba(120,170,255, 26); border-radius: 14px; color: rgba(180,230,255,170); font-weight: 800;"
                )

            cb = QCheckBox(it.title or f"Item {i+1}")
            cb.setChecked(i == 0)
            cb.setStyleSheet("QCheckBox { color: rgba(255,255,255,220); font-weight: 700; }")
            cb.setToolTip(it.url)
            row = i // max_cols
            col = i % max_cols
            cell_layout.addWidget(thumb, alignment=Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(cb, alignment=Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(cell, row, col)
            self._items.append((cb, thumb, it))

    def selected_urls(self) -> list[str]:
        out: list[str] = []
        for cb, _thumb, it in self._items:
            if cb.isChecked():
                out.append(it.url)
        return out

    def set_thumbnail_for_url(self, url: str, pix: QPixmap, *, title: Optional[str] = None) -> None:
        for cb, thumb, it in self._items:
            if it.url == url:
                if title:
                    it.title = title
                it.thumb = pix
                thumb.setText("")
                thumb.setStyleSheet(
                    "background-color: rgba(255,255,255, 10); border: 1px solid rgba(255,255,255, 18); border-radius: 14px;"
                )
                thumb.setPixmap(
                    pix.scaled(
                        140,
                        60,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                cb.setText(it.title or cb.text())
                break

    def set_title_for_url(self, url: str, title: str) -> None:
        for cb, _thumb, it in self._items:
            if it.url == url:
                it.title = title
                cb.setText(title)
                break


class HistoryManager:
    """
    Persist completed downloads for search/filter.
    Stored under: <download_dir>/.ultradl_history.json
    """

    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.path = download_dir / ".ultradl_history.json"

    def load(self) -> list[dict[str, Any]]:
        try:
            if not self.path.exists():
                return []
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def add(self, record: dict[str, Any]) -> None:
        data = self.load()
        data.insert(0, record)
        data = data[:2000]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class UltraDLMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)

        self.thread_pool = QThreadPool.globalInstance()

        self.config: AppConfig = load_config()
        self.video_downloader = VideoDownloader(self.config)

        self.history = HistoryManager(self.config.download_dir)

        # Theme
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Segoe UI", "Inter", "Roboto", Arial, sans-serif;
                background-color: rgba(10, 12, 18, 255);
            }
            """
        )

        # Toasts
        self.toast_mgr = ToastManager(self)
        self.toast_mgr.setFixedWidth(420)
        self.toast_mgr.move(self.width() - self.toast_mgr.width() - 18, 18)
        self.toast_mgr.raise_()

        self.current_url: Optional[str] = None
        self.current_title: str = "—"

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(12)
        self._left_layout = left

        self.url_card = UrlCard()
        left.addWidget(self.url_card)

        self.quality = QualitySelector()
        left.addWidget(self.quality)

        self.start_btn = QPushButton("Download")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                color: rgba(255,255,255,240);
                background: linear-gradient(135deg, rgba(80,140,255,220), rgba(160,90,255,200));
                border: 1px solid rgba(255,255,255, 14);
                border-radius: 18px;
                padding: 14px 18px;
                font-weight: 950;
            }
            QPushButton:hover { filter: brightness(1.06); }
            """
        )
        self.start_btn.clicked.connect(lambda: self._start_downloads())
        left.addWidget(self.start_btn)

        self.playlist_grid = PlaylistGrid()
        self.playlist_grid.setVisible(False)
        left.addWidget(self.playlist_grid)

        # Downloads area (scroll)
        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_container = QWidget()
        self.downloads_layout = QVBoxLayout(self.downloads_container)
        self.downloads_layout.setContentsMargins(6, 6, 6, 6)
        self.downloads_layout.setSpacing(12)
        self.downloads_layout.addStretch(1)
        self.downloads_scroll.setWidget(self.downloads_container)

        downloads_title = QLabel("Download Manager")
        downloads_title.setStyleSheet("color: rgba(255,255,255,235); font-weight: 950; font-size: 14px;")
        downloads_title_frame = QFrame()
        downloads_title_layout = QHBoxLayout(downloads_title_frame)
        downloads_title_layout.setContentsMargins(0, 0, 0, 0)
        downloads_title_layout.addWidget(downloads_title)
        downloads_title_layout.addStretch(1)

        left.addWidget(downloads_title_frame)
        left.addWidget(self.downloads_scroll, stretch=1)

        # Right settings panel
        right = QVBoxLayout()
        right.setSpacing(12)

        self.settings_frame = GlassFrame(radius=18)
        self.settings_frame.setFixedWidth(380)

        # --- Settings controls ---
        self.dir_btn = QPushButton("Choose download folder")
        self.dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dir_btn.setStyleSheet(self._settings_button_style())
        self.dir_label = QLabel(str(self.config.download_dir))
        self.dir_label.setStyleSheet("color: rgba(255,255,255,200);")

        self.max_parallel_spin = QSpinBox()
        self.max_parallel_spin.setRange(1, 16)
        self.max_parallel_spin.setValue(int(self.config.max_concurrent_downloads))
        self.max_parallel_spin.setStyleSheet(self._spin_style())

        self.default_height_combo = QComboBox()
        self.default_height_combo.setStyleSheet(self._combo_style())
        self.default_height_combo.addItems(["Auto", "144p", "360p", "720p", "1080p", "4K"])
        self.default_height_combo.setCurrentText(_tier_for_height(self.config.preferred_height))

        self.srt_check = QCheckBox("Subtitles: SRT")
        self.vtt_check = QCheckBox("Subtitles: VTT")
        self.srt_check.setChecked(True)
        self.vtt_check.setChecked(True)
        self.srt_check.setStyleSheet("QCheckBox { color: rgba(255,255,255,220); font-weight: 700; }")
        self.vtt_check.setStyleSheet("QCheckBox { color: rgba(255,255,255,220); font-weight: 700; }")

        self.thumb_check = QCheckBox("Download thumbnails")
        self.thumb_check.setChecked(True)
        self.thumb_check.setStyleSheet("QCheckBox { color: rgba(255,255,255,220); font-weight: 700; }")

        apply_btn = QPushButton("Apply Settings")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet(self._settings_button_style(accent="rgba(120,170,255, 80)"))
        apply_btn.clicked.connect(self._apply_settings)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: rgba(255,255,255,170);")

        settings_layout = QVBoxLayout(self.settings_frame)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(10)

        header = QLabel("Settings")
        header.setStyleSheet("color: rgba(255,255,255,235); font-weight: 950; font-size: 16px;")

        settings_layout.addWidget(header)
        settings_layout.addWidget(self.dir_btn)
        settings_layout.addWidget(self.dir_label)

        settings_layout.addWidget(QLabel("Max parallel downloads"))
        settings_layout.addWidget(self.max_parallel_spin)

        settings_layout.addWidget(QLabel("Default quality"))
        settings_layout.addWidget(self.default_height_combo)

        settings_layout.addWidget(self.thumb_check)
        settings_layout.addWidget(QLabel("Subtitle preferences"))
        settings_layout.addWidget(self.srt_check)
        settings_layout.addWidget(self.vtt_check)

        settings_layout.addStretch(1)
        settings_layout.addWidget(apply_btn)
        settings_layout.addWidget(self.status_label)

        right.addWidget(self.settings_frame)

        # Bottom history panel
        history_frame = GlassFrame(radius=18)
        history_frame.setFixedHeight(240)
        history_title = QLabel("History")
        history_title.setStyleSheet("color: rgba(255,255,255,235); font-weight: 950; font-size: 14px;")
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search downloaded videos…")
        self.history_search.setStyleSheet(
            """
            QLineEdit {
                color: rgba(255,255,255,235);
                background-color: rgba(255,255,255, 10);
                border: 1px solid rgba(255,255,255, 18);
                border-radius: 14px;
                padding: 10px 12px;
                font-weight: 700;
            }
            """
        )

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(
            """
            QListWidget {
                background-color: rgba(255,255,255, 7);
                border: 1px solid rgba(255,255,255, 16);
                border-radius: 14px;
            }
            QListWidget::item {
                color: rgba(255,255,255,220);
                padding: 8px 10px;
            }
            QListWidget::item:selected {
                background-color: rgba(120,170,255, 22);
            }
            """
        )
        self.history_search.textChanged.connect(self._refresh_history_list)

        hist_layout = QVBoxLayout(history_frame)
        hist_layout.setContentsMargins(14, 14, 14, 14)
        hist_layout.setSpacing(10)
        hist_layout.addWidget(history_title)
        hist_layout.addWidget(self.history_search)
        hist_layout.addWidget(self.history_list, 1)

        right.addWidget(history_frame)

        # Hook events
        self.url_card.analyze_btn.clicked.connect(self._on_analyze)

        self._refresh_history_list()

        root_layout.addLayout(left, stretch=1)
        root_layout.addLayout(right, stretch=0)

    @staticmethod
    def _settings_button_style(accent: str = "rgba(255,255,255, 14)") -> str:
        return (
            """
            QPushButton {
                color: rgba(255,255,255,240);
                background-color: rgba(255,255,255, 10);
                border: 1px solid %s;
                border-radius: 16px;
                padding: 12px 14px;
                font-weight: 900;
            }
            QPushButton:hover { background-color: rgba(255,255,255, 16); }
            """
            % accent
        )

    @staticmethod
    def _spin_style() -> str:
        return (
            """
            QSpinBox {
                color: rgba(255,255,255,235);
                background-color: rgba(255,255,255, 10);
                border: 1px solid rgba(255,255,255, 18);
                border-radius: 14px;
                padding: 10px 12px;
                font-weight: 700;
            }
            """
        )

    @staticmethod
    def _combo_style() -> str:
        return (
            """
            QComboBox {
                color: rgba(255,255,255,235);
                background-color: rgba(255,255,255, 10);
                border: 1px solid rgba(255,255,255, 18);
                border-radius: 14px;
                padding: 10px 12px;
                font-weight: 700;
            }
            """
        )

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.toast_mgr.move(self.width() - self.toast_mgr.width() - 18, 18)

    def _apply_settings(self) -> None:
        # Directory
        # Parallel downloads
        self.config.max_concurrent_downloads = int(self.max_parallel_spin.value())
        self.thread_pool.setMaxThreadCount(self.config.max_concurrent_downloads)

        # Default height
        label = self.default_height_combo.currentText()
        label = label.strip()
        mapping = {"Auto": None, "144p": 144, "360p": 360, "720p": 720, "1080p": 1080, "4K": 2160}
        self.config.preferred_height = int(mapping[label]) if mapping[label] is not None else self.config.preferred_height

        # Subtitle preferences: UI stores both toggles; job will convert to subtitle_formats set.
        self.status_label.setText("Settings applied.")
        self.toast_mgr.push("Settings applied.", kind="info")

    def _refresh_history_list(self) -> None:
        query = self.history_search.text().strip().lower()
        items = self.history.load()
        self.history_list.clear()
        for rec in items:
            title = str(rec.get("title", "")).lower()
            url = str(rec.get("url", "")).lower()
            if query and (query not in title and query not in url):
                continue
            dt = rec.get("saved_at", "")[:19].replace("T", " ")
            row = f"{rec.get('title','Untitled')}  •  {dt}"
            it = QListWidgetItem(row)
            it.setToolTip(str(rec.get("path", "")))
            self.history_list.addItem(it)

    def _on_analyze(self) -> None:
        url = self.url_card.url_text()
        if not url:
            QMessageBox.warning(self, APP_NAME, "Please paste a URL.")
            return
        self.status_label.setText("Analyzing…")
        self.toast_mgr.push("Extracting metadata…", kind="info")

        # Worker
        worker = ExtractWorker(self.video_downloader, url)
        worker.signals.finished.connect(lambda ev: self._on_analyzed(ev, url))
        worker.signals.failed.connect(self._on_analyze_failed)
        self.thread_pool.start(worker)

    def _on_analyze_failed(self, err: str) -> None:
        self.status_label.setText("Failed to analyze.")
        self.toast_mgr.push(f"Extraction failed: {err}", kind="error")
        QMessageBox.critical(self, APP_NAME, f"Extraction failed:\n{err}")

    def _on_analyzed(self, ev: Any, url: str) -> None:
        try:
            platform = str(getattr(ev, "extractor_id", "unknown") or "unknown")
            self.url_card.set_preview(platform=platform, title=getattr(ev, "title", "—"), uploader=getattr(ev, "uploader", "—"))
            self.current_url = url
            self.current_title = str(getattr(ev, "title", "—") or "—")

            # Quality options
            heights: list[int] = []
            for s in getattr(ev, "streams", []) or []:
                if s.height:
                    heights.append(int(s.height))
            # Provide a reasonable set even when no heights exist
            if not heights:
                heights = [144, 360, 720, 1080, 2160]
            self.quality.set_stream_options(heights)

            # Playlist best-effort (seed list). If seeds exist, show grid.
            related = getattr(ev, "related_pages", []) or []
            if related:
                items: list[PlaylistItem] = []
                for i, seed in enumerate(related[:18]):
                    items.append(PlaylistItem(url=getattr(seed, "url", ""), title=getattr(seed, "title_hint", "") or f"Item {i+1}"))
                self.playlist_grid.set_items(items)
                self.playlist_grid.setVisible(True)
                # Best-effort thumbnails for the first few tiles.
                for it in items[:9]:
                    w = PlaylistThumbWorker(self.video_downloader, it.url)

                    def _ok(u: str, payload: dict, *, _url: str = it.url) -> None:
                        title = str(payload.get("title") or "")
                        thumb_bytes = payload.get("thumb_bytes")
                        if title:
                            self.playlist_grid.set_title_for_url(u, title)
                        if thumb_bytes:
                            pix = QPixmap()
                            pix.loadFromData(thumb_bytes)
                            if not pix.isNull():
                                self.playlist_grid.set_thumbnail_for_url(u, pix, title=title or None)

                    def _fail(_u: str, _err: str) -> None:
                        return

                    w.signals.finished.connect(_ok)
                    w.signals.failed.connect(_fail)
                    self.thread_pool.start(w)
            else:
                self.playlist_grid.setVisible(False)

            self.status_label.setText("Preview ready. Start downloads from the playlist or single URL.")
            self.start_btn.setText("Download Selected" if self.playlist_grid.isVisible() else "Download")
        except Exception as exc:
            self.toast_mgr.push(f"UI update error: {exc}", kind="error")
            log.error("UI update failed: %s", exc)

    def _subtitle_formats_from_settings(self) -> tuple[bool, Optional[set[str]]]:
        srt = bool(self.srt_check.isChecked())
        vtt = bool(self.vtt_check.isChecked())
        if not srt and not vtt:
            return False, None
        allowed: set[str] = set()
        if srt:
            allowed.add("srt")
        if vtt:
            allowed.add("vtt")
        return True, allowed

    def _start_downloads(self) -> None:
        if not self.current_url:
            QMessageBox.warning(self, APP_NAME, "Analyze a URL first.")
            return

        dl_dir = Path(self.config.download_dir)
        dl_dir.mkdir(parents=True, exist_ok=True)

        download_subs, subtitle_formats = self._subtitle_formats_from_settings()
        download_thumbnail = bool(self.thumb_check.isChecked())

        preferred_height = self.quality.selected_height() or self.config.preferred_height
        output_format = self.quality.output_format()
        live = self.quality.live_enabled()

        urls = [self.current_url]
        if self.playlist_grid.isVisible():
            urls = self.playlist_grid.selected_urls() or [self.current_url]
            self.toast_mgr.push(f"Playlist queued: {len(urls)} items", kind="info")

        # Create cards and spawn download workers
        for u in urls:
            title = safe_filename(u.split("?", 1)[0].rstrip("/").split("/")[-1] or "video")
            if u == self.current_url:
                title = safe_filename(self.current_title) or title
            card = DownloadCardWidget(title)

            # Insert above stretch
            # downloads_layout has stretch as last item.
            insert_idx = max(0, self.downloads_layout.count() - 1)
            self.downloads_layout.insertWidget(insert_idx, card)
            # Subtle fade-in animation (does not impact download performance)
            effect = QGraphicsOpacityEffect(card)
            card.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            anim = QPropertyAnimation(effect, b"opacity", card)
            anim.setDuration(360)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            card.set_status("Starting…")

            worker = DownloadWorker(
                self.video_downloader,
                u,
                output_dir=dl_dir,
                preferred_height=preferred_height,
                output_format=output_format,
                live=live,
                download_thumbnail=download_thumbnail,
                download_subs=download_subs,
                subtitle_formats=subtitle_formats,
                stop_event=card.stop_event,
                pause_event=card.pause_event,
            )
            worker.signals.started.connect(lambda _: card.set_status("Downloading…"))

            worker.signals.progress.connect(lambda meta, c=card: c.update_progress(meta))

            def _done(res: Any, c=card) -> None:
                c.set_status("Completed", ok=True)
                self.toast_mgr.push(f"Finished: {getattr(res, 'output_path', '')}", kind="success")
                # History entry
                try:
                    out_path = getattr(res, "output_path", None)
                    self.history.add(
                        {
                            "title": getattr(getattr(res, "extracted", None), "title", c._title),
                            "url": u,
                            "format": output_format,
                            "height": preferred_height,
                            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "path": str(out_path) if out_path else "",
                        }
                    )
                    self._refresh_history_list()
                except Exception:
                    pass

            def _failed(err: str, c=card) -> None:
                if card.stop_event.is_set():
                    c.set_status("Cancelled", ok=False)
                else:
                    c.set_status(f"Failed", ok=False)
                self.toast_mgr.push(f"Download failed: {err}", kind="error")

            worker.signals.finished.connect(_done)
            worker.signals.failed.connect(_failed)
            self.thread_pool.start(worker)


def launch_gui() -> None:
    app = QApplication.instance() or QApplication([])
    theme_path = Path(__file__).with_name("theme_dark.qss")
    if theme_path.exists():
        try:
            app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    win = UltraDLMainWindow()
    win.show()
    app.exec()

