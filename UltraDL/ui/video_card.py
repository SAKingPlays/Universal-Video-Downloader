"""
Video-related card components - preview cards and download item cards.
"""

from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QPixmap, QColor, QFont

from .styles import COLORS, FONTS
from .base_card import AnimatedCard
from .progress import WaveProgressRing, SpeedGraph, CircularButton
from .buttons import SecondaryButton, DangerButton


class VideoPreviewCard(AnimatedCard):
    """
    Video preview card showing thumbnail, title, and metadata.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=18, animate_on_show=False)
        self._thumbnail: Optional[QPixmap] = None
        self._setup_ui()
        self.hide()  # Hidden until video is analyzed
    
    def _setup_ui(self):
        """Setup the preview card UI."""
        self.setMinimumHeight(140)
        self.setMaximumHeight(160)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        
        # Thumbnail
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(160, 90)
        self._thumb_label.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 10);
            border-radius: 12px;
            border: 1px solid {COLORS.GLASS_BORDER};
        """)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setScaledContents(True)
        layout.addWidget(self._thumb_label)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        
        self._platform_label = QLabel("Platform: —")
        self._platform_label.setStyleSheet(f"""
            color: {COLORS.TEXT_ACCENT};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
            font-weight: {FONTS.WEIGHT_SEMIBOLD};
        """)
        info_layout.addWidget(self._platform_label)
        
        self._title_label = QLabel("Title: —")
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_MEDIUM};
            font-weight: {FONTS.WEIGHT_BOLD};
        """)
        info_layout.addWidget(self._title_label)
        
        self._uploader_label = QLabel("Uploader: —")
        self._uploader_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
        """)
        info_layout.addWidget(self._uploader_label)
        
        self._duration_label = QLabel("Duration: —")
        self._duration_label.setStyleSheet(f"""
            color: {COLORS.TEXT_MUTED};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        info_layout.addWidget(self._duration_label)
        
        info_layout.addStretch(1)
        layout.addLayout(info_layout, stretch=1)
    
    def set_video_info(
        self, 
        title: str, 
        platform: str, 
        uploader: str = "",
        duration: str = "",
        thumbnail: Optional[QPixmap] = None
    ):
        """Update the preview with video information."""
        self._title_label.setText(title)
        self._platform_label.setText(f"Detected: {platform}")
        self._uploader_label.setText(f"Uploader: {uploader or '—'}")
        self._duration_label.setText(f"Duration: {duration or '—'}")
        
        if thumbnail and not thumbnail.isNull():
            self._thumbnail = thumbnail.scaled(
                160, 90,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self._thumb_label.setPixmap(self._thumbnail)
        else:
            self._thumb_label.setText("📹")
            self._thumb_label.setStyleSheet(f"""
                background-color: rgba(120, 170, 255, 15);
                border-radius: 12px;
                border: 1px solid rgba(120, 170, 255, 40);
                color: {COLORS.TEXT_ACCENT};
                font-size: 24px;
            """)
        
        self.show()
        # Animation handled by AnimatedCard on initial show
    
    def clear(self):
        """Clear the preview."""
        self._title_label.setText("Title: —")
        self._platform_label.setText("Detected: —")
        self._uploader_label.setText("Uploader: —")
        self._duration_label.setText("Duration: —")
        self._thumb_label.clear()
        self._thumbnail = None
        self.hide()


class DownloadItemCard(AnimatedCard):
    """
    Download item card with progress ring, speed graph, and controls.
    """
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent, radius=16, animate_on_show=True)
        self._title = title
        self._status = "queued"
        self._is_paused = False
        
        # Control callbacks
        self.on_pause: Optional[Callable] = None
        self.on_resume: Optional[Callable] = None
        self.on_cancel: Optional[Callable] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the download card UI."""
        self.setMinimumHeight(130)
        self.setMaximumHeight(140)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)
        
        # Thumbnail placeholder
        self._thumb_label = QLabel("📹")
        self._thumb_label.setFixedSize(100, 56)
        self._thumb_label.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 10);
            border-radius: 10px;
            border: 1px solid {COLORS.GLASS_BORDER};
            color: {COLORS.TEXT_MUTED};
            font-size: 20px;
        """)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._thumb_label)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self._title_label = QLabel(self._title)
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
            font-weight: {FONTS.WEIGHT_BOLD};
        """)
        info_layout.addWidget(self._title_label)
        
        self._status_label = QLabel("Queued")
        self._status_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        info_layout.addWidget(self._status_label)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self._speed_label = QLabel("— MiB/s")
        self._speed_label.setStyleSheet(f"""
            color: {COLORS.TEXT_ACCENT};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
            font-weight: {FONTS.WEIGHT_SEMIBOLD};
        """)
        stats_layout.addWidget(self._speed_label)
        
        self._eta_label = QLabel("ETA: —")
        self._eta_label.setStyleSheet(f"""
            color: {COLORS.TEXT_MUTED};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        stats_layout.addWidget(self._eta_label)
        stats_layout.addStretch(1)
        
        info_layout.addLayout(stats_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        self._pause_btn = SecondaryButton("Pause", self)
        self._pause_btn.setMinimumWidth(70)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        controls_layout.addWidget(self._pause_btn)
        
        self._cancel_btn = DangerButton("Cancel", self)
        self._cancel_btn.setMinimumWidth(70)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        controls_layout.addWidget(self._cancel_btn)
        
        controls_layout.addStretch(1)
        info_layout.addLayout(controls_layout)
        
        layout.addLayout(info_layout, stretch=1)
        
        # Progress section
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)
        
        self._progress_ring = WaveProgressRing(size=70)
        progress_layout.addWidget(self._progress_ring, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self._speed_graph = SpeedGraph()
        progress_layout.addWidget(self._speed_graph)
        
        layout.addLayout(progress_layout)
    
    def _on_pause_clicked(self):
        """Handle pause/resume button click."""
        self._is_paused = not self._is_paused
        
        if self._is_paused:
            self._pause_btn.setText("Resume")
            self._status_label.setText("Paused")
            self._status_label.setStyleSheet(f"""
                color: {COLORS.WARNING};
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_SMALL};
            """)
            if self.on_pause:
                self.on_pause()
        else:
            self._pause_btn.setText("Pause")
            self._status_label.setText("Downloading...")
            self._status_label.setStyleSheet(f"""
                color: {COLORS.TEXT_SECONDARY};
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_SMALL};
            """)
            if self.on_resume:
                self.on_resume()
    
    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        self._pause_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("Cancelling...")
        self._status_label.setStyleSheet(f"""
            color: {COLORS.ERROR};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        if self.on_cancel:
            self.on_cancel()
    
    def update_progress(self, percentage: float, speed_mbps: float = 0.0, eta_seconds: int = 0):
        """Update download progress."""
        speed_bytes = speed_mbps * 1024 * 1024
        self._progress_ring.set_progress(percentage, speed_bytes)
        self._speed_graph.add_point(speed_mbps)
        
        self._speed_label.setText(f"{speed_mbps:.2f} MiB/s")
        
        if eta_seconds > 0:
            mins, secs = divmod(eta_seconds, 60)
            self._eta_label.setText(f"ETA: {mins}:{secs:02d}")
        else:
            self._eta_label.setText("ETA: —")
        
        if percentage >= 100:
            self._set_completed()
    
    def _set_completed(self):
        """Mark download as completed."""
        self._pause_btn.setEnabled(False)
        self._status_label.setText("Completed")
        self._status_label.setStyleSheet(f"""
            color: {COLORS.SUCCESS};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        self._eta_label.setText("Done")
        self._speed_label.setText("—")
    
    def set_error(self, error_message: str):
        """Mark download as failed."""
        self._pause_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(f"Failed: {error_message[:30]}")
        self._status_label.setStyleSheet(f"""
            color: {COLORS.ERROR};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
    
    def set_thumbnail(self, pixmap: QPixmap):
        """Set the thumbnail image."""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                100, 56,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self._thumb_label.setPixmap(scaled)
            self._thumb_label.setStyleSheet(f"""
                background-color: transparent;
                border-radius: 10px;
                border: 1px solid {COLORS.GLASS_BORDER};
            """)
