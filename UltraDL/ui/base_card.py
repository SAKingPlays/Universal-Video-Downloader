"""
Base card components with glassmorphism and animation effects.
"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSize
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

from .styles import COLORS, ANIMATION


class GlassCard(QFrame):
    """
    Glassmorphism card with subtle border and background.
    Base class for all card-like UI components.
    """
    
    def __init__(self, parent=None, radius: int = 16):
        super().__init__(parent)
        self._radius = radius
        self._setup_appearance()
    
    def _setup_appearance(self):
        """Apply glass card styling."""
        self.setStyleSheet(f"""
            GlassCard {{
                background-color: {COLORS.GLASS_BG};
                border: 1px solid {COLORS.GLASS_BORDER};
                border-radius: {self._radius}px;
            }}
        """)
        self.setObjectName("GlassCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class AnimatedCard(GlassCard):
    """
    Glass card with entrance and hover animations.
    """
    
    def __init__(self, parent=None, radius: int = 16, animate_on_show: bool = True):
        super().__init__(parent, radius)
        self._animate_on_show = animate_on_show
        self._opacity_effect = None
        self._shadow_effect = None
        self._has_animated = False
        
        self._setup_effects()
        
        if animate_on_show:
            self._play_entrance_animation()
    
    def _setup_effects(self):
        """Setup shadow effect only (opacity handled per-animation)."""
        # Shadow effect for card elevation
        self._shadow_effect = QGraphicsDropShadowEffect(self)
        self._shadow_effect.setBlurRadius(20)
        self._shadow_effect.setColor(QColor(0, 0, 0, 100))
        self._shadow_effect.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow_effect)
    
    def _play_entrance_animation(self):
        """Play fade-in animation when card appears."""
        if self._has_animated:
            return
        
        self._has_animated = True
        
        # Create fresh opacity effect for this animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        
        # Need to temporarily replace the shadow effect with opacity
        # Store reference to shadow and restore after animation
        shadow = self._shadow_effect
        self.setGraphicsEffect(self._opacity_effect)
        
        # Fade in animation
        fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade_anim.setDuration(ANIMATION.DURATION_SLOW)
        fade_anim.setStartValue(0.0)
        fade_anim.setEndValue(1.0)
        fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # When animation finishes, restore shadow effect
        def on_finished():
            self._opacity_effect = None
            self.setGraphicsEffect(shadow)
        
        fade_anim.finished.connect(on_finished)
        fade_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def fade_out(self, duration: int = ANIMATION.DURATION_NORMAL, callback=None):
        """
        Fade out the card and optionally call a callback when done.
        """
        # Create opacity effect for fade out
        opacity_effect = QGraphicsOpacityEffect(self)
        opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(opacity_effect)
        
        fade_anim = QPropertyAnimation(opacity_effect, b"opacity", self)
        fade_anim.setDuration(duration)
        fade_anim.setStartValue(1.0)
        fade_anim.setEndValue(0.0)
        fade_anim.setEasingCurve(QEasingCurve.InCubic)
        
        if callback:
            fade_anim.finished.connect(callback)
        
        fade_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def set_glow(self, enabled: bool, color: QColor = None):
        """
        Enable or disable glow effect around the card.
        """
        if enabled:
            color = color or QColor(COLORS.ACCENT_BLUE)
            self._shadow_effect.setColor(color)
            self._shadow_effect.setBlurRadius(30)
            self._shadow_effect.setOffset(0, 0)
        else:
            self._shadow_effect.setColor(QColor(0, 0, 0, 100))
            self._shadow_effect.setBlurRadius(20)
            self._shadow_effect.setOffset(0, 4)
