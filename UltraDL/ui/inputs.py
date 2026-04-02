"""
Modern input components with animations and validation.
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QLineEdit, QTextEdit
from PySide6.QtGui import QFocusEvent

from .styles import COLORS, FONTS, ANIMATION, StyleSheet


class ModernLineEdit(QLineEdit):
    """
    Modern styled line edit with focus animations.
    """
    
    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self._styles = StyleSheet()
        self.setStyleSheet(self._styles.input_field())
        
        if placeholder:
            self.setPlaceholderText(placeholder)
        
        self.setMinimumHeight(40)
    
    def focusInEvent(self, event: QFocusEvent):
        """Animate on focus."""
        super().focusInEvent(event)
        # Could add focus animation here


class ModernTextEdit(QTextEdit):
    """
    Modern styled text edit for multi-line input.
    """
    
    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self._styles = StyleSheet()
        self.setStyleSheet(self._styles.text_edit())
        
        if placeholder:
            self.setPlaceholderText(placeholder)
        
        self.setMinimumHeight(80)


class SearchInput(QLineEdit):
    """
    Search input with icon placeholder and clear button.
    """
    
    def __init__(self, parent=None, placeholder: str = "Search..."):
        super().__init__(parent)
        self._styles = StyleSheet()
        
        # Add search icon as placeholder text with unicode
        self.setPlaceholderText(f"🔍  {placeholder}")
        
        self.setStyleSheet(f"""
            QLineEdit {{
                color: {COLORS.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: 20px;
                padding: 10px 16px 10px 16px;
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_NORMAL};
                font-weight: {FONTS.WEIGHT_MEDIUM};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS.GLASS_BORDER_ACTIVE};
                background-color: rgba(120, 170, 255, 10);
            }}
        """)
        
        self.setMinimumHeight(40)
        
        # Add clear button
        self.setClearButtonEnabled(True)


class UrlInput(QLineEdit):
    """
    Specialized URL input with paste button and validation.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._styles = StyleSheet()
        
        self.setPlaceholderText("Paste video URL here...")
        self.setStyleSheet(f"""
            QLineEdit {{
                color: {COLORS.TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: 16px;
                padding: 14px 18px;
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_MEDIUM};
                font-weight: {FONTS.WEIGHT_MEDIUM};
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS.GLASS_BORDER_ACTIVE};
                background-color: rgba(120, 170, 255, 12);
            }}
        """)
        
        self.setMinimumHeight(50)
