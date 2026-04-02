"""
UltraDL Modern UI Components Package
Reusable, animated UI components for the premium video downloader interface.
"""

from .styles import COLORS, FONTS, ANIMATION, StyleSheet
from .base_card import GlassCard, AnimatedCard
from .buttons import GradientButton, SecondaryButton, DangerButton, IconButton, ActionChip
from .inputs import ModernLineEdit, ModernTextEdit, SearchInput, UrlInput
from .progress import WaveProgressRing, SmoothProgressBar, SpeedGraph
from .notification import ToastNotification, NotificationManager
from .video_card import VideoPreviewCard, DownloadItemCard
from .navigation import NavigationBar
from .dialogs import ModernFileDialog

__all__ = [
    # Styles
    "COLORS", "FONTS", "ANIMATION", "StyleSheet",
    # Base Components
    "GlassCard", "AnimatedCard",
    # Buttons
    "GradientButton", "SecondaryButton", "DangerButton", "IconButton", "ActionChip",
    # Inputs
    "ModernLineEdit", "ModernTextEdit", "SearchInput", "UrlInput",
    # Progress
    "WaveProgressRing", "SmoothProgressBar", "SpeedGraph",
    # Notifications
    "ToastNotification", "NotificationManager",
    # Video Cards
    "VideoPreviewCard", "DownloadItemCard",
    # Navigation
    "NavigationBar",
    # Dialogs
    "ModernFileDialog",
]
