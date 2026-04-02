"""
Toast notification system with animations.
"""

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect
from PySide6.QtGui import QColor

from .styles import COLORS, FONTS, ANIMATION
from .base_card import GlassCard


class ToastNotification(GlassCard):
    """
    Individual toast notification widget.
    """
    
    KIND_COLORS = {
        "info": COLORS.INFO,
        "success": COLORS.SUCCESS,
        "warning": COLORS.WARNING,
        "error": COLORS.ERROR,
    }
    
    KIND_ICONS = {
        "info": "ℹ️",
        "success": "✓",
        "warning": "⚠",
        "error": "✕",
    }
    
    def __init__(self, message: str, kind: str = "info", parent=None):
        super().__init__(parent, radius=14)
        self._message = message
        self._kind = kind
        
        self._setup_ui()
        self._setup_animation()
    
    def _setup_ui(self):
        """Setup the notification UI."""
        # Style based on kind
        color = self.KIND_COLORS.get(self._kind, COLORS.INFO)
        
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: rgba(24, 26, 38, 220);
                border: 1px solid {color.replace('200)', '40)')};
                border-radius: 14px;
                padding: 0px;
            }}
        """)
        
        self.setFixedHeight(50)
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QLabel(self.KIND_ICONS.get(self._kind, "ℹ️"))
        icon_label.setStyleSheet(f"""
            color: {color};
            font-size: 14px;
            font-weight: bold;
        """)
        layout.addWidget(icon_label)
        
        # Message
        self._label = QLabel(self._message)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"""
            color: {COLORS.TEXT_PRIMARY};
            font-family: {FONTS.FAMILY};
            font-size: {FONTS.SIZE_NORMAL};
            font-weight: {FONTS.WEIGHT_MEDIUM};
        """)
        layout.addWidget(self._label, stretch=1)
    
    def _setup_animation(self):
        """Setup entrance animation."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Fade in animation
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(ANIMATION.DURATION_NORMAL)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def fade_out(self, callback=None):
        """Fade out and remove."""
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(ANIMATION.DURATION_NORMAL)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        
        if callback:
            anim.finished.connect(callback)
        
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class NotificationManager(QWidget):
    """
    Manages a stack of toast notifications.
    Positions notifications in the top-right corner.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the manager widget."""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Layout for stacking notifications
        from PySide6.QtWidgets import QVBoxLayout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        
        self.setFixedWidth(360)
    
    def push(self, message: str, kind: str = "info", duration_ms: int = None):
        """
        Show a new notification.
        
        Args:
            message: The message to display
            kind: "info", "success", "warning", or "error"
            duration_ms: How long to show (default 3500ms)
        """
        duration = duration_ms or ANIMATION.DURATION_TOAST
        
        toast = ToastNotification(message, kind, self)
        
        # Insert above the stretch
        insert_idx = self._layout.count() - 1
        self._layout.insertWidget(insert_idx, toast)
        self._notifications.append(toast)
        
        # Position manager in top-right of parent
        self._update_position()
        
        # Auto-remove after duration
        QTimer.singleShot(duration, lambda: self._remove_toast(toast))
    
    def _remove_toast(self, toast: ToastNotification):
        """Remove a toast with animation."""
        if toast in self._notifications:
            self._notifications.remove(toast)
            
            def cleanup():
                toast.deleteLater()
                self._layout.update()
            
            toast.fade_out(cleanup)
    
    def _update_position(self):
        """Update position relative to parent."""
        if self.parent():
            parent_width = self.parent().width()
            self.move(parent_width - self.width() - 20, 20)
    
    def resizeEvent(self, event):
        """Reposition on resize."""
        super().resizeEvent(event)
        self._update_position()
