"""
Modern progress indicators with animations.
"""

import math
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import QWidget, QProgressBar
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QLinearGradient, QPixmap

from .styles import COLORS, FONTS


class WaveProgressRing(QWidget):
    """
    Animated circular progress ring with wave effects.
    Shows percentage and supports speed display.
    """
    
    def __init__(self, parent=None, size: int = 100):
        super().__init__(parent)
        self._size = size
        self._progress = 0.0
        self._speed_mbps = 0.0
        self._phase = 0.0
        
        self.setFixedSize(QSize(size, size))
        self.setMinimumSize(QSize(size, size))
        
        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(32)  # ~30fps
    
    def set_progress(self, percentage: float, speed_bytes_per_sec: float = 0.0):
        """Update progress (0-100) and speed."""
        self._progress = max(0.0, min(100.0, percentage))
        self._speed_mbps = speed_bytes_per_sec / (1024 * 1024)
        self.update()
    
    def _tick(self):
        """Animation frame update."""
        self._phase += 0.07
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0
        radius = min(width, height) * 0.4
        
        # Background ring
        bg_pen = QPen(QColor(255, 255, 255, 25), 6)
        painter.setPen(bg_pen)
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(2 * radius),
            int(2 * radius)
        )
        
        # Progress arc with gradient
        arc_span = int(360 * (self._progress / 100.0))
        gradient = QLinearGradient(
            int(center_x - radius), int(center_y - radius),
            int(center_x + radius), int(center_y + radius)
        )
        gradient.setColorAt(0.0, QColor(110, 170, 255, 255))
        gradient.setColorAt(1.0, QColor(155, 110, 255, 255))
        
        prog_pen = QPen(gradient, 6)
        painter.setPen(prog_pen)
        
        # Draw progress arc (Qt uses 1/16 degrees, starting at 3 o'clock)
        painter.drawArc(
            int(center_x - radius),
            int(center_y - radius),
            int(2 * radius),
            int(2 * radius),
            -90 * 16,
            -arc_span * 16
        )
        
        # Wave highlight points
        wave_color = QColor(255, 255, 255, 60)
        for i in range(6):
            angle = -90 + (i * 360 / 6)
            rad = math.radians(angle + self._phase * 20.0 * (0.4 + self._progress / 100.0))
            r_wave = radius * (0.92 + 0.05 * math.sin(self._phase + i))
            x = center_x + math.cos(rad) * r_wave
            y = center_y + math.sin(rad) * r_wave
            painter.setPen(QPen(wave_color, 2))
            painter.drawPoint(int(x), int(y))
        
        # Center percentage text
        painter.setPen(QColor(240, 244, 255, 230))
        font = QFont(FONTS.FAMILY.replace('"', ''), 14)
        font.setBold(True)
        painter.setFont(font)
        
        pct_text = "—" if self._progress <= 0 else f"{int(self._progress)}%"
        text_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignCenter, pct_text)
        text_x = int(center_x - text_rect.width() / 2)
        text_y = int(center_y + text_rect.height() / 2 - 4)
        painter.drawText(text_x, text_y, pct_text)


class SmoothProgressBar(QProgressBar):
    """
    Smooth animated horizontal progress bar.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setMinimumHeight(6)
        self.setMaximumHeight(6)
        
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 15);
                border-radius: 3px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS.GRADIENT_START},
                    stop:1 {COLORS.GRADIENT_END});
                border-radius: 3px;
            }}
        """)


class SpeedGraph(QWidget):
    """
    Real-time speed graph showing download speed over time.
    """
    
    def __init__(self, parent=None, max_points: int = 60):
        super().__init__(parent)
        self._max_points = max_points
        self._points = []
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
    
    def add_point(self, mbps: float):
        """Add a new speed data point."""
        self._points.append(float(max(0.0, mbps)))
        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points:]
        self.update()
    
    def clear(self):
        """Clear all data points."""
        self._points = []
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        w = self.width()
        h = self.height()
        
        # Transparent background
        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 0))
        
        # Border
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)
        
        if len(self._points) < 2:
            return
        
        # Calculate scale
        max_y = max(self._points) or 1.0
        max_y = max(max_y, 1.0)  # At least 1 MB/s scale
        
        step = w / max(1, (self._max_points - 1))
        
        # Draw line
        pen = QPen(QColor(110, 170, 255, 230), 2)
        painter.setPen(pen)
        
        points = []
        start_x = w - step * (len(self._points) - 1)
        
        for i, val in enumerate(self._points):
            x = start_x + i * step
            y = h - (val / max_y) * (h - 14) - 7
            points.append((x, y))
        
        # Draw connected lines
        for i in range(1, len(points)):
            x1, y1 = points[i - 1]
            x2, y2 = points[i]
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Draw current value dot
        if points:
            x, y = points[-1]
            painter.setBrush(QColor(155, 110, 255, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)


class CircularButton(QWidget):
    """
    Circular action button with icon.
    Used for pause/resume/cancel in download cards.
    """
    
    def __init__(self, icon_text: str, color: str, parent=None, size: int = 32):
        super().__init__(parent)
        self._icon_text = icon_text
        self._color = color
        self._size = size
        self._hover = False
        
        self.setFixedSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Background
        bg_color = QColor(self._color)
        if self._hover:
            bg_color.setAlpha(80)
        else:
            bg_color.setAlpha(50)
        
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self._size - 1, self._size - 1)
        
        # Icon text
        painter.setPen(QColor(255, 255, 255, 230))
        font = QFont(FONTS.FAMILY.replace('"', ''), 12)
        font.setBold(True)
        painter.setFont(font)
        
        text_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignCenter, self._icon_text)
        text_x = int((self._size - text_rect.width()) / 2)
        text_y = int((self._size + text_rect.height()) / 2 - 3)
        painter.drawText(text_x, text_y, self._icon_text)
