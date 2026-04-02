"""
Modern button components with gradients, animations, and hover effects.
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor, QIcon

from .styles import COLORS, FONTS, ANIMATION, StyleSheet


class GradientButton(QPushButton):
    """
    Primary action button with gradient background.
    Used for main actions like Download, Analyze.
    """
    
    def __init__(self, text: str, parent=None, radius: int = 14):
        super().__init__(text, parent)
        self._radius = radius
        self._styles = StyleSheet()
        self._setup_ui()
    
    def _setup_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._styles.gradient_button(self._radius))
        
        # Add shadow effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(15)
        self._shadow.setColor(QColor(80, 140, 255, 100))
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)
        
        # Minimum size for consistency
        self.setMinimumHeight(44)
    
    def enterEvent(self, event):
        """Animate shadow on hover."""
        super().enterEvent(event)
        anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        anim.setDuration(ANIMATION.DURATION_FAST)
        anim.setStartValue(self._shadow.blurRadius())
        anim.setEndValue(25)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def leaveEvent(self, event):
        """Reset shadow on leave."""
        super().leaveEvent(event)
        anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        anim.setDuration(ANIMATION.DURATION_FAST)
        anim.setStartValue(self._shadow.blurRadius())
        anim.setEndValue(15)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class SecondaryButton(QPushButton):
    """
    Secondary action button with subtle background.
    Used for actions like Cancel, Back.
    """
    
    def __init__(self, text: str, parent=None, radius: int = 12):
        super().__init__(text, parent)
        self._styles = StyleSheet()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._styles.secondary_button(radius))
        self.setMinimumHeight(36)


class DangerButton(QPushButton):
    """
    Danger action button with red accent.
    Used for destructive actions like Delete, Cancel Download.
    """
    
    def __init__(self, text: str, parent=None, radius: int = 12):
        super().__init__(text, parent)
        self._styles = StyleSheet()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._styles.danger_button(radius))
        self.setMinimumHeight(36)


class IconButton(QPushButton):
    """
    Circular button with just an icon.
    Used for navigation, settings, close buttons.
    """
    
    def __init__(self, icon_path: str = None, parent=None, size: int = 36):
        super().__init__(parent)
        self._size = size
        self._setup_ui()
        
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(size - 12, size - 12))
    
    def _setup_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._size, self._size)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: {self._size // 2}px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 40);
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 5);
            }}
        """)


class ActionChip(QPushButton):
    """
    Toggleable chip button for selecting options.
    Used for quality selection, format options.
    """
    
    def __init__(self, text: str, parent=None, checkable: bool = True):
        super().__init__(text, parent)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy()
        )
        self._update_style()
        
        # Connect state change
        self.toggled.connect(self._on_toggled)
    
    def _update_style(self):
        """Update style based on check state."""
        checked_style = f"""
            background-color: rgba(120, 170, 255, 25);
            border: 1px solid rgba(120, 170, 255, 80);
            color: {COLORS.TEXT_PRIMARY};
        """ if self.isChecked() else f"""
            background-color: rgba(255, 255, 255, 10);
            border: 1px solid {COLORS.GLASS_BORDER};
            color: {COLORS.TEXT_SECONDARY};
        """
        
        self.setStyleSheet(f"""
            QPushButton {{
                {checked_style}
                border-radius: 14px;
                padding: 6px 14px;
                font-family: {FONTS.FAMILY};
                font-size: {FONTS.SIZE_SMALL};
                font-weight: {FONTS.WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 18);
            }}
        """)
    
    def _on_toggled(self, checked: bool):
        """Handle toggle state change."""
        self._update_style()
