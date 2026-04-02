"""
UltraDL Modern GUI Application
A premium video downloader interface with modern design, animations, and full functionality.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from PySide6.QtCore import (
    QObject, QRunnable, QThreadPool, Qt, QTimer, Signal, QSize, QRect,
    QPropertyAnimation, QEasingCurve, QAbstractAnimation
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea, QStackedWidget, QComboBox, QCheckBox,
    QSpinBox, QFileDialog, QMessageBox, QSizePolicy, QGridLayout,
    QGraphicsOpacityEffect
)
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon

try:
    from PySide6.QtCore import QCoreApplication
except ImportError:
    pass

# Import UltraDL components
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from UltraDL.core.downloader import DownloadSession, VideoDownloader
from UltraDL.utils.config_loader import AppConfig, default_config_path, load_config
from UltraDL.utils.logger import get_logger
from UltraDL.utils.file_utils import safe_filename
from UltraDL.extractors.base_extractor import ExtractorContext, ExtractedVideo, StreamCandidate, StreamKind

# Import modern UI components
from UltraDL.ui import (
    COLORS, FONTS, StyleSheet, ANIMATION,
    GlassCard, AnimatedCard,
    GradientButton, SecondaryButton, DangerButton, ActionChip,
    ModernLineEdit, SearchInput, UrlInput,
    WaveProgressRing, SmoothProgressBar, SpeedGraph,
    NotificationManager,
    VideoPreviewCard, DownloadItemCard,
    NavigationBar,
    ModernFileDialog,
)

log = get_logger("gui.modern")

APP_NAME = "UltraDL"
VERSION = "2.0.0"


# ============================================================================
# Worker Thread Components
# ============================================================================

class ExtractWorkerSignals(QObject):
    """Signals for extraction worker."""
    finished = Signal(object)  # ExtractedVideo
    failed = Signal(str)       # Error message
    progress = Signal(str)     # Status message


class ExtractWorker(QRunnable):
    """Worker for extracting video metadata in background."""
    
    def __init__(self, downloader: VideoDownloader, url: str):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.signals = ExtractWorkerSignals()
        self.setAutoDelete(True)
    
    def run(self):
        """Run extraction."""
        try:
            self.signals.progress.emit("Extracting metadata...")
            result = self.downloader.extract(self.url, use_cache=True)
            self.signals.finished.emit(result)
        except Exception as exc:
            log.error("Extraction failed: %s", exc)
            self.signals.failed.emit(str(exc))


class DownloadWorkerSignals(QObject):
    """Signals for download worker."""
    started = Signal()
    progress = Signal(dict)   # Progress metadata
    finished = Signal(object)   # DownloadResult
    failed = Signal(str)        # Error message


class DownloadWorker(QRunnable):
    """Worker for downloading videos in background."""
    
    def __init__(
        self,
        downloader: VideoDownloader,
        url: str,
        output_dir: Path,
        preferred_height: Optional[int],
        output_format: str,
        download_thumbnail: bool = True,
        download_subs: bool = True,
        subtitle_formats: Optional[Set[str]] = None,
        live: bool = False,
        stop_event: threading.Event = None,
        pause_event: threading.Event = None,
    ):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.preferred_height = preferred_height
        self.output_format = output_format
        self.download_thumbnail = download_thumbnail
        self.download_subs = download_subs
        self.subtitle_formats = subtitle_formats
        self.live = live
        self.stop_event = stop_event or threading.Event()
        self.pause_event = pause_event or threading.Event()
        self.pause_event.set()  # Not paused by default
        self.signals = DownloadWorkerSignals()
        self.setAutoDelete(True)
    
    def run(self):
        """Run download."""
        try:
            self.signals.started.emit()
            
            session = DownloadSession(self.downloader)
            result = session.run(
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
            
            self.signals.finished.emit(result)
        except Exception as exc:
            log.error("Download failed: %s", exc)
            self.signals.failed.emit(str(exc))


# ============================================================================
# Panel Components
# ============================================================================

class UrlInputPanel(GlassCard):
    """
    URL input panel with modern design and analyze button.
    """
    
    analyze_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=20)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the URL input panel."""
        self.setMinimumHeight(140)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        
        # Header
        header = QLabel("Download Video")
        header.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_TITLE};
            font-weight: {FONTS.WEIGHT_EXTRABOLD};
        """)
        layout.addWidget(header)
        
        # URL Input row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)
        
        # URL input field
        self._url_input = UrlInput()
        self._url_input.setPlaceholderText("Paste video URL here (YouTube, Vimeo, etc.)")
        self._url_input.returnPressed.connect(self._on_analyze)
        input_layout.addWidget(self._url_input, stretch=1)
        
        # Analyze button
        self._analyze_btn = GradientButton("Analyze", radius=14)
        self._analyze_btn.setMinimumWidth(100)
        self._analyze_btn.clicked.connect(self._on_analyze)
        input_layout.addWidget(self._analyze_btn)
        
        layout.addLayout(input_layout)
    
    def _on_analyze(self):
        """Handle analyze button click."""
        self.analyze_clicked.emit()
    
    def get_url(self) -> str:
        """Get the entered URL."""
        return self._url_input.text().strip()
    
    def set_loading(self, loading: bool):
        """Set loading state."""
        self._analyze_btn.setEnabled(not loading)
        self._analyze_btn.setText("Analyzing..." if loading else "Analyze")
    
    def clear(self):
        """Clear the input."""
        self._url_input.clear()


class QualityPanel(GlassCard):
    """
    Quality selection panel with resolution chips and format dropdown.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=18)
        self._height_map = {
            "Auto": None,
            "144p": 144,
            "240p": 240,
            "360p": 360,
            "480p": 480,
            "720p": 720,
            "1080p": 1080,
            "1440p": 1440,
            "4K": 2160,
        }
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the quality panel."""
        self.setMinimumHeight(140)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        # Header row
        header_layout = QHBoxLayout()
        
        header = QLabel("Quality & Format")
        header.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_LARGE};
            font-weight: {FONTS.WEIGHT_BOLD};
        """)
        header_layout.addWidget(header)
        header_layout.addStretch(1)
        
        layout.addLayout(header_layout)
        
        # Resolution chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        
        res_label = QLabel("Resolution:")
        res_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
        """)
        chips_layout.addWidget(res_label)
        
        self._resolution_chips: Dict[str, ActionChip] = {}
        resolutions = ["Auto", "360p", "720p", "1080p", "4K"]
        
        for res in resolutions:
            chip = ActionChip(res)
            chip.setCheckable(True)
            chip.setChecked(res == "Auto")
            chip.clicked.connect(lambda checked, r=res: self._on_resolution_clicked(r, checked))
            self._resolution_chips[res] = chip
            chips_layout.addWidget(chip)
        
        chips_layout.addStretch(1)
        layout.addLayout(chips_layout)
        
        # Format and options row
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)
        
        # Format dropdown
        format_label = QLabel("Format:")
        format_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
        """)
        options_layout.addWidget(format_label)
        
        self._format_combo = QComboBox()
        self._format_combo.addItems(["mp4", "mkv", "webm"])
        self._format_combo.setMinimumWidth(80)
        styles = StyleSheet()
        self._format_combo.setStyleSheet(styles.combo_box())
        options_layout.addWidget(self._format_combo)
        
        options_layout.addSpacing(20)
        
        # Options checkboxes
        self._subs_check = QCheckBox("Download subtitles")
        self._subs_check.setStyleSheet(styles.check_box())
        self._subs_check.setChecked(True)
        options_layout.addWidget(self._subs_check)
        
        self._thumb_check = QCheckBox("Download thumbnail")
        self._thumb_check.setStyleSheet(styles.check_box())
        self._thumb_check.setChecked(True)
        options_layout.addWidget(self._thumb_check)
        
        self._live_check = QCheckBox("Live stream mode")
        self._live_check.setStyleSheet(styles.check_box())
        options_layout.addWidget(self._live_check)
        
        options_layout.addStretch(1)
        layout.addLayout(options_layout)
    
    def _on_resolution_clicked(self, resolution: str, checked: bool):
        """Handle resolution chip click."""
        if checked:
            # Uncheck others
            for res, chip in self._resolution_chips.items():
                if res != resolution:
                    chip.setChecked(False)
    
    def get_selected_height(self) -> Optional[int]:
        """Get selected resolution height."""
        for res, chip in self._resolution_chips.items():
            if chip.isChecked():
                return self._height_map.get(res)
        return None
    
    def get_format(self) -> str:
        """Get selected format."""
        return self._format_combo.currentText()
    
    def get_options(self) -> Dict[str, bool]:
        """Get download options."""
        return {
            "subtitles": self._subs_check.isChecked(),
            "thumbnail": self._thumb_check.isChecked(),
            "live": self._live_check.isChecked(),
        }


class DownloadsPanel(GlassCard):
    """
    Downloads manager panel showing active download cards.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=18)
        self._download_cards: Dict[str, DownloadItemCard] = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the downloads panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("Active Downloads")
        header.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_LARGE};
            font-weight: {FONTS.WEIGHT_BOLD};
        """)
        header_layout.addWidget(header)
        header_layout.addStretch(1)
        
        self._count_label = QLabel("0")
        self._count_label.setStyleSheet(f"""
            color: {COLORS.TEXT_MUTED};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
            background-color: rgba(255, 255, 255, 10);
            padding: 2px 10px;
            border-radius: 10px;
        """)
        header_layout.addWidget(self._count_label)
        
        layout.addLayout(header_layout)
        
        # Scroll area for download cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(StyleSheet().scroll_area())
        self._scroll.setMinimumHeight(200)
        self._scroll.setMaximumHeight(400)
        
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(4, 4, 4, 4)
        self._container_layout.setSpacing(10)
        self._container_layout.addStretch(1)
        
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)
    
    def add_download(self, download_id: str, title: str) -> DownloadItemCard:
        """Add a new download card."""
        card = DownloadItemCard(title)
        
        # Insert above the stretch
        insert_idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(insert_idx, card)
        
        self._download_cards[download_id] = card
        self._update_count()
        
        return card
    
    def remove_download(self, download_id: str):
        """Remove a download card."""
        if download_id in self._download_cards:
            card = self._download_cards[download_id]
            
            # Fade out animation
            effect = QGraphicsOpacityEffect(card)
            card.setGraphicsEffect(effect)
            
            anim = QPropertyAnimation(effect, b"opacity", card)
            anim.setDuration(ANIMATION.DURATION_NORMAL)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.InCubic)
            
            def cleanup():
                self._container_layout.removeWidget(card)
                card.deleteLater()
                del self._download_cards[download_id]
                self._update_count()
            
            anim.finished.connect(cleanup)
            anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def get_card(self, download_id: str) -> Optional[DownloadItemCard]:
        """Get a download card by ID."""
        return self._download_cards.get(download_id)
    
    def _update_count(self):
        """Update the download count label."""
        count = len(self._download_cards)
        self._count_label.setText(str(count))


class SettingsPanel(GlassCard):
    """
    Settings panel with folder selector and configuration options.
    """
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=18)
        self._current_folder = Path.home() / "Downloads"
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the settings panel."""
        self.setMinimumWidth(320)
        self.setMaximumWidth(360)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        
        # Header
        header = QLabel("⚙️ Settings")
        header.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_TITLE};
            font-weight: {FONTS.WEIGHT_EXTRABOLD};
        """)
        layout.addWidget(header)
        
        # Download folder section
        folder_header = QLabel("Download Folder")
        folder_header.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
            font-weight: {FONTS.WEIGHT_SEMIBOLD};
        """)
        layout.addWidget(folder_header)
        
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(8)
        
        self._folder_label = QLabel(str(self._current_folder))
        self._folder_label.setWordWrap(True)
        self._folder_label.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
            background-color: rgba(255, 255, 255, 8);
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid {COLORS.GLASS_BORDER};
        """)
        folder_layout.addWidget(self._folder_label, stretch=1)
        
        self._folder_btn = SecondaryButton("Browse", radius=10)
        self._folder_btn.setMinimumWidth(70)
        self._folder_btn.clicked.connect(self._on_select_folder)
        folder_layout.addWidget(self._folder_btn)
        
        layout.addLayout(folder_layout)
        
        # Parallel downloads
        parallel_layout = QHBoxLayout()
        
        parallel_label = QLabel("Max Parallel Downloads:")
        parallel_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
        """)
        parallel_layout.addWidget(parallel_label)
        
        self._parallel_spin = QSpinBox()
        self._parallel_spin.setRange(1, 8)
        self._parallel_spin.setValue(3)
        self._parallel_spin.setStyleSheet(f"""
            QSpinBox {{
                color: {COLORS.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: 10px;
                padding: 6px 10px;
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_NORMAL};
                font-weight: {FONTS.WEIGHT_SEMIBOLD};
                min-width: 50px;
            }}
        """)
        self._parallel_spin.valueChanged.connect(self._on_setting_changed)
        parallel_layout.addWidget(self._parallel_spin)
        parallel_layout.addStretch(1)
        
        layout.addLayout(parallel_layout)
        
        # Default quality
        quality_layout = QHBoxLayout()
        
        quality_label = QLabel("Default Quality:")
        quality_label.setStyleSheet(f"""
            color: {COLORS.TEXT_SECONDARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
        """)
        quality_layout.addWidget(quality_label)
        
        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["Auto", "360p", "720p", "1080p", "4K"])
        self._quality_combo.setCurrentText("Auto")
        styles = StyleSheet()
        self._quality_combo.setStyleSheet(styles.combo_box())
        self._quality_combo.currentTextChanged.connect(self._on_setting_changed)
        quality_layout.addWidget(self._quality_combo)
        quality_layout.addStretch(1)
        
        layout.addLayout(quality_layout)
        
        # Spacer
        layout.addStretch(1)
        
        # Save button
        self._save_btn = GradientButton("Save Settings", radius=12)
        self._save_btn.setMinimumHeight(40)
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._save_btn)
    
    def _on_select_folder(self):
        """Handle folder selection."""
        folder = ModernFileDialog.select_folder(
            self.parent(),
            "Select Download Folder",
            str(self._current_folder)
        )
        
        if folder:
            self._current_folder = folder
            self._folder_label.setText(str(folder))
            self.settings_changed.emit()
    
    def _on_setting_changed(self):
        """Handle any setting change."""
        self.settings_changed.emit()
    
    def _on_save(self):
        """Handle save button click."""
        # Could persist settings to file here
        self.settings_changed.emit()
    
    def get_download_folder(self) -> Path:
        """Get the selected download folder."""
        return self._current_folder
    
    def get_max_parallel(self) -> int:
        """Get max parallel downloads."""
        return self._parallel_spin.value()
    
    def get_default_quality(self) -> Optional[int]:
        """Get default quality."""
        text = self._quality_combo.currentText()
        mapping = {"Auto": None, "360p": 360, "720p": 720, "1080p": 1080, "4K": 2160}
        return mapping.get(text)
    
    def set_download_folder(self, folder: Path):
        """Set the download folder."""
        self._current_folder = folder
        self._folder_label.setText(str(folder))


class HistoryPanel(GlassCard):
    """
    Download history panel with search and filtering.
    """
    
    item_selected = Signal(str)  # URL of selected item
    
    def __init__(self, parent=None):
        super().__init__(parent, radius=18)
        self._history_items: List[Dict[str, Any]] = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the history panel."""
        self.setMinimumHeight(200)
        self.setMaximumHeight(300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("📜 Download History")
        header.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_LARGE};
            font-weight: {FONTS.WEIGHT_BOLD};
        """)
        header_layout.addWidget(header)
        header_layout.addStretch(1)
        
        self._count_label = QLabel("0 items")
        self._count_label.setStyleSheet(f"""
            color: {COLORS.TEXT_MUTED};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
        """)
        header_layout.addWidget(self._count_label)
        
        layout.addLayout(header_layout)
        
        # Search input
        self._search_input = SearchInput(placeholder="Search history...")
        self._search_input.textChanged.connect(self._on_search)
        layout.addWidget(self._search_input)
        
        # History list
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self._list = QListWidget()
        styles = StyleSheet()
        self._list.setStyleSheet(styles.list_widget())
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)
    
    def _on_search(self, text: str):
        """Handle search text change."""
        self._refresh_list(text.lower())
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle history item click."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_selected.emit(data.get("url", ""))
    
    def _refresh_list(self, filter_text: str = ""):
        """Refresh the history list with optional filter."""
        self._list.clear()
        
        count = 0
        for item in self._history_items:
            title = item.get("title", "Unknown")
            url = item.get("url", "")
            date = item.get("saved_at", "")[:16].replace("T", " ")
            
            # Filter
            if filter_text and filter_text not in title.lower() and filter_text not in url.lower():
                continue
            
            display = f"{title} • {date}"
            list_item = QListWidgetItem(display)
            list_item.setToolTip(url)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self._list.addItem(list_item)
            count += 1
        
        self._count_label.setText(f"{count} items")
    
    def set_history(self, items: List[Dict[str, Any]]):
        """Set the history items."""
        self._history_items = items
        self._refresh_list()
    
    def add_history_item(self, item: Dict[str, Any]):
        """Add a new history item."""
        self._history_items.insert(0, item)
        # Limit to 200 items
        self._history_items = self._history_items[:200]
        self._refresh_list()


# ============================================================================
# History Manager
# ============================================================================

class HistoryManager:
    """
    Persist download history to disk.
    """
    
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.path = download_dir / ".ultradl_history.json"
    
    def load(self) -> List[Dict[str, Any]]:
        """Load history from disk."""
        try:
            if not self.path.exists():
                return []
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Failed to load history: %s", exc)
            return []
    
    def save(self, data: List[Dict[str, Any]]) -> None:
        """Save history to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            log.error("Failed to save history: %s", exc)
    
    def add(self, record: Dict[str, Any]) -> None:
        """Add a record to history."""
        data = self.load()
        data.insert(0, record)
        data = data[:200]
        self.save(data)


# ============================================================================
# Main Window
# ============================================================================

class ModernMainWindow(QMainWindow):
    """
    UltraDL Modern Main Window
    Premium video downloader interface with modern design.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 700)
        
        # Initialize thread pool
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)
        
        # Initialize downloader
        self.config: AppConfig = load_config()
        self.downloader = VideoDownloader(self.config)
        
        # Initialize history
        self.history_manager = HistoryManager(self.config.download_dir)
        
        # Track active downloads
        self._active_downloads: Dict[str, Dict[str, Any]] = {}
        self._download_counter = 0
        
        # Currently analyzed video
        self._current_extracted: Optional[ExtractedVideo] = None
        self._current_url: str = ""
        
        self._setup_ui()
        self._apply_global_styles()
        self._load_history()
    
    def _setup_ui(self):
        """Setup the main window UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Navigation bar
        self._nav_bar = NavigationBar()
        self._nav_bar.settings_clicked.connect(self._on_settings_clicked)
        main_layout.addWidget(self._nav_bar)
        
        # Content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)
        
        # Left column - Main download area
        left_column = QVBoxLayout()
        left_column.setSpacing(14)
        
        # URL input panel
        self._url_panel = UrlInputPanel()
        self._url_panel.analyze_clicked.connect(self._on_analyze)
        left_column.addWidget(self._url_panel)
        
        # Video preview card
        self._preview_card = VideoPreviewCard()
        left_column.addWidget(self._preview_card)
        
        # Quality panel
        self._quality_panel = QualityPanel()
        left_column.addWidget(self._quality_panel)
        
        # Download button
        self._download_btn = GradientButton("⬇️ Start Download", radius=16)
        self._download_btn.setMinimumHeight(50)
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._on_start_download)
        left_column.addWidget(self._download_btn)
        
        left_column.addStretch(1)
        
        # Downloads panel
        self._downloads_panel = DownloadsPanel()
        left_column.addWidget(self._downloads_panel, stretch=2)
        
        content_layout.addLayout(left_column, stretch=2)
        
        # Right column - Settings and History
        right_column = QVBoxLayout()
        right_column.setSpacing(14)
        
        # Settings panel
        self._settings_panel = SettingsPanel()
        self._settings_panel.set_download_folder(self.config.download_dir)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        right_column.addWidget(self._settings_panel)
        
        # History panel
        self._history_panel = HistoryPanel()
        self._history_panel.item_selected.connect(self._on_history_selected)
        right_column.addWidget(self._history_panel, stretch=1)
        
        right_column.addStretch(1)
        
        content_layout.addLayout(right_column, stretch=1)
        
        main_layout.addWidget(content_widget, stretch=1)
        
        # Notification manager
        self._notifications = NotificationManager(self)
        self._notifications.raise_()
    
    def _apply_global_styles(self):
        """Apply global application styles."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS.BG_PRIMARY};
            }}
            QWidget {{
                font-family: {FONTS.FAMILY};
            }}
        """)
    
    def _load_history(self):
        """Load download history."""
        history = self.history_manager.load()
        self._history_panel.set_history(history)
    
    def resizeEvent(self, event):
        """Handle resize to reposition notifications."""
        super().resizeEvent(event)
        if hasattr(self, '_notifications'):
            self._notifications.setGeometry(
                self.width() - 380, 80, 360, self.height() - 100
            )
    
    # ========================================================================
    # Event Handlers
    # ========================================================================
    
    def _on_analyze(self):
        """Handle URL analysis."""
        url = self._url_panel.get_url()
        
        if not url:
            self._notifications.push("Please enter a video URL", "warning")
            return
        
        self._url_panel.set_loading(True)
        self._notifications.push("Analyzing video...", "info")
        
        # Create worker
        worker = ExtractWorker(self.downloader, url)
        worker.signals.finished.connect(self._on_analyze_finished)
        worker.signals.failed.connect(self._on_analyze_failed)
        
        self.thread_pool.start(worker)
    
    def _on_analyze_finished(self, result: ExtractedVideo):
        """Handle successful analysis."""
        self._current_extracted = result
        self._current_url = result.canonical_url
        
        self._url_panel.set_loading(False)
        
        # Update preview card
        duration = self._format_duration(getattr(result, "duration", None))
        
        # Try to get thumbnail
        thumbs = getattr(result, "thumbnail_urls", [])
        thumb_pixmap = None
        if thumbs:
            try:
                import httpx
                resp = httpx.get(thumbs[0], timeout=10)
                if resp.status_code == 200:
                    thumb_pixmap = QPixmap()
                    thumb_pixmap.loadFromData(resp.content)
            except Exception:
                pass
        
        self._preview_card.set_video_info(
            title=result.title or "Unknown",
            platform=result.extractor_id or "Unknown",
            uploader=result.uploader or "",
            duration=duration,
            thumbnail=thumb_pixmap
        )
        
        # Enable download button
        self._download_btn.setEnabled(True)
        
        self._notifications.push(f"Found: {result.title}", "success")
    
    def _on_analyze_failed(self, error: str):
        """Handle analysis failure."""
        self._url_panel.set_loading(False)
        self._notifications.push(f"Analysis failed: {error}", "error")
    
    def _on_start_download(self):
        """Handle download start."""
        if not self._current_url or not self._current_extracted:
            self._notifications.push("Please analyze a video first", "warning")
            return
        
        # Get settings
        output_dir = self._settings_panel.get_download_folder()
        preferred_height = self._quality_panel.get_selected_height()
        output_format = self._quality_panel.get_format()
        options = self._quality_panel.get_options()
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create download ID
        self._download_counter += 1
        download_id = f"dl_{self._download_counter}"
        
        # Create control events
        stop_event = threading.Event()
        pause_event = threading.Event()
        pause_event.set()
        
        # Add download card
        title = safe_filename(self._current_extracted.title or "video")[:50]
        card = self._downloads_panel.add_download(download_id, title)
        
        # Connect card controls
        def on_pause():
            pause_event.clear()
        
        def on_resume():
            pause_event.set()
        
        def on_cancel():
            stop_event.set()
        
        card.on_pause = on_pause
        card.on_resume = on_resume
        card.on_cancel = on_cancel
        
        # Store download info
        self._active_downloads[download_id] = {
            "card": card,
            "stop_event": stop_event,
            "pause_event": pause_event,
            "url": self._current_url,
        }
        
        # Determine subtitle formats
        subtitle_formats = None
        if options.get("subtitles"):
            subtitle_formats = {"srt", "vtt"}
        
        # Create worker
        worker = DownloadWorker(
            self.downloader,
            self._current_url,
            output_dir,
            preferred_height=preferred_height,
            output_format=output_format,
            download_thumbnail=options.get("thumbnail", True),
            download_subs=options.get("subtitles", True),
            subtitle_formats=subtitle_formats,
            live=options.get("live", False),
            stop_event=stop_event,
            pause_event=pause_event,
        )
        
        # Connect signals
        worker.signals.progress.connect(
            lambda meta: self._on_download_progress(download_id, meta)
        )
        worker.signals.finished.connect(
            lambda result: self._on_download_finished(download_id, result)
        )
        worker.signals.failed.connect(
            lambda error: self._on_download_failed(download_id, error)
        )
        
        # Start download
        self.thread_pool.start(worker)
        
        self._notifications.push(f"Download started: {title}", "success")
    
    def _on_download_progress(self, download_id: str, meta: Dict[str, float]):
        """Handle download progress update."""
        download_info = self._active_downloads.get(download_id)
        if not download_info:
            return
        
        card = download_info["card"]
        
        pct = meta.get("pct", 0.0)
        speed = meta.get("speed", 0.0) / (1024 * 1024)  # Convert to MB/s
        eta = meta.get("eta", 0.0)
        
        card.update_progress(pct, speed, int(eta))
    
    def _on_download_finished(self, download_id: str, result):
        """Handle download completion."""
        download_info = self._active_downloads.get(download_id)
        if not download_info:
            return
        
        card = download_info["card"]
        card.update_progress(100.0, 0.0, 0)
        
        # Add to history
        history_item = {
            "title": card._title,
            "url": download_info["url"],
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "path": str(getattr(result, "output_path", "")),
        }
        self.history_manager.add(history_item)
        self._history_panel.add_history_item(history_item)
        
        # Clean up after delay
        QTimer.singleShot(5000, lambda: self._downloads_panel.remove_download(download_id))
        
        self._notifications.push(f"Download complete: {card._title}", "success")
        
        # Remove from active downloads
        if download_id in self._active_downloads:
            del self._active_downloads[download_id]
    
    def _on_download_failed(self, download_id: str, error: str):
        """Handle download failure."""
        download_info = self._active_downloads.get(download_id)
        if not download_info:
            return
        
        card = download_info["card"]
        card.set_error(error)
        
        self._notifications.push(f"Download failed: {error}", "error")
        
        # Remove from active downloads
        if download_id in self._active_downloads:
            del self._active_downloads[download_id]
    
    def _on_settings_clicked(self):
        """Handle settings button click."""
        # Scroll to settings or open settings dialog
        self._notifications.push("Settings are in the right panel", "info")
    
    def _on_settings_changed(self):
        """Handle settings change."""
        # Update thread pool size
        max_parallel = self._settings_panel.get_max_parallel()
        self.thread_pool.setMaxThreadCount(max_parallel)
        
        # Update config
        self.config.download_dir = self._settings_panel.get_download_folder()
        self.config.max_concurrent_downloads = max_parallel
        
        self._notifications.push("Settings updated", "success")
    
    def _on_history_selected(self, url: str):
        """Handle history item selection."""
        self._url_panel._url_input.setText(url)
        self._on_analyze()
    
    def _format_duration(self, seconds: Optional[int]) -> str:
        """Format duration in seconds to string."""
        if not seconds:
            return "—"
        mins, secs = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"
    
    def closeEvent(self, event):
        """Handle window close."""
        # Cancel all active downloads
        for download_id, download_info in list(self._active_downloads.items()):
            download_info["stop_event"].set()
        
        # Save settings
        try:
            # Could save to config file here
            pass
        except Exception:
            pass
        
        event.accept()


# ============================================================================
# Application Entry Point
# ============================================================================

def launch_modern_gui():
    """Launch the modern UltraDL GUI."""
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
    
    # Create and show window
    window = ModernMainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_modern_gui()
