"""
Navigation bar component with logo, title, and action buttons.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtGui import QFont

from .styles import COLORS, FONTS
from .buttons import IconButton


class NavigationBar(QWidget):
    """
    Top navigation bar with logo, title, settings, and theme toggle.
    """
    
    # Signals
    settings_clicked = Signal()
    theme_toggled = Signal(bool)  # True for dark, False for light
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = True
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        """Setup the navigation bar UI."""
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(16)
        
        # Logo and Title section
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(10)
        
        # Logo icon (using emoji as placeholder, can be replaced with actual icon)
        self._logo_label = QLabel("⬇️")
        self._logo_label.setStyleSheet("font-size: 24px;")
        logo_layout.addWidget(self._logo_label)
        
        # Title
        self._title_label = QLabel("UltraDL")
        self._title_label.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: 20px;
            font-weight: {FONTS.WEIGHT_EXTRABOLD};
        """)
        logo_layout.addWidget(self._title_label)
        
        # Subtitle
        self._subtitle_label = QLabel("Universal Video Downloader")
        self._subtitle_label.setStyleSheet(f"""
            color: {COLORS.TEXT_MUTED};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_SMALL};
            font-weight: {FONTS.WEIGHT_MEDIUM};
        """)
        logo_layout.addWidget(self._subtitle_label)
        logo_layout.addStretch(1)
        
        layout.addLayout(logo_layout, stretch=1)
        
        # Spacer
        layout.addStretch(2)
        
        # Action buttons section
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # Theme toggle button
        self._theme_btn = QPushButton("🌙")  # Moon for dark mode
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setStyleSheet(self._icon_button_style())
        self._theme_btn.setToolTip("Toggle theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        buttons_layout.addWidget(self._theme_btn)
        
        # Settings button
        self._settings_btn = QPushButton("⚙️")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(self._icon_button_style())
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        buttons_layout.addWidget(self._settings_btn)
        
        layout.addLayout(buttons_layout)
    
    def _apply_style(self):
        """Apply navigation bar styling."""
        self.setStyleSheet(f"""
            NavigationBar {{
                background-color: {COLORS.BG_SECONDARY};
                border-bottom: 1px solid {COLORS.GLASS_BORDER};
            }}
        """)
        self.setObjectName("NavigationBar")
    
    def _icon_button_style(self) -> str:
        """Get style for icon buttons."""
        return f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: 18px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 40);
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 5);
            }}
        """
    
    def _toggle_theme(self):
        """Toggle between dark and light theme."""
        self._is_dark = not self._is_dark
        self._theme_btn.setText("🌙" if self._is_dark else "☀️")
        self.theme_toggled.emit(self._is_dark)
    
    def set_dark_mode(self, is_dark: bool):
        """Set the theme mode."""
        self._is_dark = is_dark
        self._theme_btn.setText("🌙" if is_dark else "☀️")
