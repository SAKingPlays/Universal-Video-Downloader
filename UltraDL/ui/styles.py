"""
UltraDL Modern Theme System
Colors, fonts, and animation constants for the premium dark theme.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class Colors:
    # Background Colors
    BG_PRIMARY: str = "#0a0c12"
    BG_SECONDARY: str = "#12151f"
    BG_TERTIARY: str = "#1a1d2a"
    BG_CARD: str = "rgba(24, 26, 38, 180)"
    BG_CARD_HOVER: str = "rgba(28, 31, 45, 200)"
    
    # Glass Effect
    GLASS_BG: str = "rgba(24, 26, 38, 160)"
    GLASS_BORDER: str = "rgba(255, 255, 255, 22)"
    GLASS_BORDER_ACTIVE: str = "rgba(120, 170, 255, 55)"
    
    # Accent Colors - Blue to Purple Gradient
    ACCENT_BLUE: str = "#508cff"
    ACCENT_PURPLE: str = "#a05aff"
    ACCENT_CYAN: str = "#00d4ff"
    
    # Gradient Stops
    GRADIENT_START: str = "rgba(80, 140, 255, 220)"
    GRADIENT_END: str = "rgba(160, 90, 255, 200)"
    
    # Text Colors
    TEXT_PRIMARY: str = "rgba(255, 255, 255, 240)"
    TEXT_SECONDARY: str = "rgba(255, 255, 255, 180)"
    TEXT_MUTED: str = "rgba(255, 255, 255, 120)"
    TEXT_ACCENT: str = "rgba(180, 230, 255, 220)"
    
    # Status Colors
    SUCCESS: str = "rgba(120, 255, 170, 200)"
    WARNING: str = "rgba(255, 200, 100, 200)"
    ERROR: str = "rgba(255, 100, 100, 200)"
    INFO: str = "rgba(120, 170, 255, 200)"
    
    # Progress Colors
    PROGRESS_BG: str = "rgba(255, 255, 255, 25)"
    PROGRESS_FILL_START: str = "#6eaa7f"
    PROGRESS_FILL_END: str = "#9b6eff"
    
    # Shadow
    SHADOW_COLOR: str = "rgba(0, 0, 0, 160)"
    GLOW_COLOR: str = "rgba(80, 140, 255, 80)"


@dataclass(frozen=True)
class Fonts:
    FAMILY: str = '"Segoe UI", "Inter", "Roboto", -apple-system, BlinkMacSystemFont, sans-serif'
    
    # Sizes
    SIZE_TINY: str = "11px"
    SIZE_SMALL: str = "12px"
    SIZE_NORMAL: str = "13px"
    SIZE_MEDIUM: str = "14px"
    SIZE_LARGE: str = "16px"
    SIZE_TITLE: str = "18px"
    SIZE_HEADER: str = "22px"
    
    # Weights
    WEIGHT_NORMAL: str = "400"
    WEIGHT_MEDIUM: str = "500"
    WEIGHT_SEMIBOLD: str = "600"
    WEIGHT_BOLD: str = "700"
    WEIGHT_EXTRABOLD: str = "800"


@dataclass(frozen=True)
class Animation:
    # Durations (ms)
    DURATION_FAST: int = 150
    DURATION_NORMAL: int = 250
    DURATION_SLOW: int = 400
    DURATION_TOAST: int = 3500
    
    # Easing
    EASING_STANDARD: str = "cubic-bezier(0.4, 0.0, 0.2, 1)"
    EASING_DECELERATE: str = "cubic-bezier(0.0, 0.0, 0.2, 1)"
    EASING_ACCELERATE: str = "cubic-bezier(0.4, 0.0, 1, 1)"
    EASING_BOUNCE: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"


class StyleSheet:
    """Generate QSS stylesheets dynamically."""
    
    def __init__(self, colors: Colors = None, fonts: Fonts = None):
        self.colors = colors or Colors()
        self.fonts = fonts or Fonts()
    
    def glass_card(self, radius: int = 16) -> str:
        return f"""
            background-color: {self.colors.GLASS_BG};
            border: 1px solid {self.colors.GLASS_BORDER};
            border-radius: {radius}px;
        """
    
    def gradient_button(self, radius: int = 14) -> str:
        return f"""
            QPushButton {{
                color: {self.colors.TEXT_PRIMARY};
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self.colors.GRADIENT_START},
                    stop:1 {self.colors.GRADIENT_END});
                border: 1px solid rgba(255, 255, 255, 14);
                border-radius: {radius}px;
                padding: 12px 24px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_MEDIUM};
                font-weight: {self.fonts.WEIGHT_BOLD};
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(100, 160, 255, 240),
                    stop:1 rgba(180, 110, 255, 220));
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(60, 120, 235, 240),
                    stop:1 rgba(140, 70, 235, 220));
            }}
            QPushButton:disabled {{
                background: rgba(255, 255, 255, 20);
                color: rgba(255, 255, 255, 100);
            }}
        """
    
    def secondary_button(self, radius: int = 12) -> str:
        return f"""
            QPushButton {{
                color: {self.colors.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {self.colors.GLASS_BORDER};
                border-radius: {radius}px;
                padding: 8px 16px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 16);
                border: 1px solid rgba(255, 255, 255, 30);
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 8);
            }}
        """
    
    def danger_button(self, radius: int = 12) -> str:
        return f"""
            QPushButton {{
                color: {self.colors.TEXT_PRIMARY};
                background-color: rgba(255, 90, 90, 60);
                border: 1px solid rgba(255, 90, 90, 80);
                border-radius: {radius}px;
                padding: 8px 16px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 90, 90, 80);
            }}
        """
    
    def input_field(self, radius: int = 14) -> str:
        return f"""
            QLineEdit {{
                color: {self.colors.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {self.colors.GLASS_BORDER};
                border-radius: {radius}px;
                padding: 10px 14px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_MEDIUM};
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors.GLASS_BORDER_ACTIVE};
                background-color: rgba(120, 170, 255, 10);
            }}
            QLineEdit::placeholder {{
                color: {self.colors.TEXT_MUTED};
            }}
        """
    
    def text_edit(self, radius: int = 16) -> str:
        return f"""
            QTextEdit {{
                color: {self.colors.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {self.colors.GLASS_BORDER};
                border-radius: {radius}px;
                padding: 12px 14px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_MEDIUM};
            }}
            QTextEdit:focus {{
                border: 1px solid {self.colors.GLASS_BORDER_ACTIVE};
                background-color: rgba(120, 170, 255, 10);
            }}
        """
    
    def combo_box(self, radius: int = 12) -> str:
        return f"""
            QComboBox {{
                color: {self.colors.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {self.colors.GLASS_BORDER};
                border-radius: {radius}px;
                padding: 8px 12px;
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_SEMIBOLD};
                min-width: 80px;
            }}
            QComboBox:hover {{
                background-color: rgba(255, 255, 255, 14);
            }}
            QComboBox::drop-down {{
                border: 0px;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.colors.BG_SECONDARY};
                color: {self.colors.TEXT_PRIMARY};
                border: 1px solid {self.colors.GLASS_BORDER};
                border-radius: 8px;
                selection-background-color: rgba(120, 170, 255, 30);
            }}
        """
    
    def check_box(self) -> str:
        return f"""
            QCheckBox {{
                color: {self.colors.TEXT_SECONDARY};
                font-family: {self.fonts.FAMILY};
                font-size: {self.fonts.SIZE_NORMAL};
                font-weight: {self.fonts.WEIGHT_MEDIUM};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {self.colors.GLASS_BORDER};
                background-color: rgba(255, 255, 255, 10);
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors.ACCENT_BLUE};
                border: 1px solid {self.colors.ACCENT_BLUE};
            }}
        """
    
    def scroll_area(self) -> str:
        return f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: rgba(255, 255, 255, 5);
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: rgba(255, 255, 255, 30);
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: rgba(255, 255, 255, 50);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """
    
    def list_widget(self, radius: int = 12) -> str:
        return f"""
            QListWidget {{
                background-color: rgba(255, 255, 255, 7);
                border: 1px solid rgba(255, 255, 255, 16);
                border-radius: {radius}px;
                outline: none;
                padding: 4px;
            }}
            QListWidget::item {{
                color: {self.colors.TEXT_SECONDARY};
                padding: 10px 12px;
                border-radius: 8px;
                margin: 2px 4px;
            }}
            QListWidget::item:hover {{
                background-color: rgba(255, 255, 255, 10);
            }}
            QListWidget::item:selected {{
                background-color: rgba(120, 170, 255, 25);
                color: {self.colors.TEXT_PRIMARY};
            }}
        """


# Global instances
COLORS = Colors()
FONTS = Fonts()
ANIMATION = Animation()
