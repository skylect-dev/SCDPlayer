"""Themed tooltip system for consistent app-wide tooltips."""
from PyQt5.QtWidgets import QWidget, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QColor, QPainter, QPainterPath


class ThemedTooltip(QWidget):
    """Themed tooltip widget that matches the app's dark theme.
    
    Features:
    - Smooth fade in/out animations
    - Customizable delay and duration
    - Auto-positioning relative to mouse or widget
    - Dark theme styling with shadow
    """
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Animation properties
        self._tooltip_opacity = 0.0
        self._fade_animation = None
        
        # Timing
        self._show_delay = 500  # ms before showing
        self._hide_delay = 200  # ms before hiding after mouse leaves
        self._show_timer = QTimer()
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_tooltip)
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_tooltip)
        
        # Content
        self._text = ""
        self._position = QPoint()
        
        # Styling
        self.bg_color = QColor(40, 40, 40, 245)
        self.border_color = QColor(100, 100, 100)
        self.text_color = QColor(220, 220, 220)
        self.padding = 8
        self.border_radius = 6
        
        # Don't use drop shadow effect - causes UpdateLayeredWindow errors
        # Instead, we'll draw the shadow manually in paintEvent
    
    @pyqtProperty(float)
    def tooltipOpacity(self):
        return self._tooltip_opacity
    
    @tooltipOpacity.setter
    def tooltipOpacity(self, value):
        self._tooltip_opacity = value
        self.update()
    
    def setText(self, text: str):
        """Set tooltip text."""
        self._text = text
        self._update_size()
    
    def _update_size(self):
        """Calculate and set size based on text."""
        if not self._text:
            return
        
        # Create temporary painter to measure text
        font = self.font()
        font.setPixelSize(11)
        
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        
        # Calculate size with padding (add extra space for manual shadow)
        text_width = fm.horizontalAdvance(self._text)
        text_height = fm.height()
        
        shadow_margin = 4  # Space for manual shadow
        width = text_width + (self.padding * 2) + shadow_margin
        height = text_height + (self.padding * 2) + shadow_margin
        
        self.setFixedSize(width, height)
    
    def showAt(self, pos: QPoint, delay: int = None):
        """Show tooltip at specific position after delay.
        
        Args:
            pos: Global position to show tooltip
            delay: Optional delay in ms (uses default if None)
        """
        self._position = pos
        
        if delay is not None:
            self._show_delay = delay
        
        # Cancel any pending hide
        self._hide_timer.stop()
        
        # Start show timer
        self._show_timer.start(self._show_delay)
    
    def _show_tooltip(self):
        """Internal method to show tooltip with animation."""
        if not self._text:
            return
        
        # Position tooltip (offset slightly from cursor)
        offset = QPoint(10, 15)
        self.move(self._position + offset)
        
        # Show and animate
        self.show()
        self.raise_()
        
        # Fade in animation
        if self._fade_animation:
            self._fade_animation.stop()
        
        self._fade_animation = QPropertyAnimation(self, b"tooltipOpacity")
        self._fade_animation.setDuration(150)
        self._fade_animation.setStartValue(self._tooltip_opacity)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_animation.start()
    
    def hideTooltip(self, delay: int = None):
        """Hide tooltip after delay.
        
        Args:
            delay: Optional delay in ms (uses default if None)
        """
        # Cancel show timer
        self._show_timer.stop()
        
        if delay is not None:
            self._hide_delay = delay
        
        if self._hide_delay > 0:
            self._hide_timer.start(self._hide_delay)
        else:
            self._hide_tooltip()
    
    def _hide_tooltip(self):
        """Internal method to hide tooltip with animation."""
        if self._fade_animation:
            self._fade_animation.stop()
        
        self._fade_animation = QPropertyAnimation(self, b"tooltipOpacity")
        self._fade_animation.setDuration(100)
        self._fade_animation.setStartValue(self._tooltip_opacity)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.InCubic)
        self._fade_animation.finished.connect(self.hide)
        self._fade_animation.start()
    
    def paintEvent(self, event):
        """Paint the tooltip."""
        if self._tooltip_opacity <= 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._tooltip_opacity)
        
        # Shadow dimensions
        shadow_offset = 2
        shadow_blur = 3
        
        # Draw manual shadow (multiple layers for blur effect)
        shadow_color = QColor(0, 0, 0, 40)
        for i in range(shadow_blur):
            shadow_path = QPainterPath()
            shadow_rect = self.rect().adjusted(
                shadow_offset + i, 
                shadow_offset + i, 
                -(shadow_blur - i), 
                -(shadow_blur - i)
            )
            shadow_path.addRoundedRect(
                shadow_rect.x(), shadow_rect.y(),
                shadow_rect.width(), shadow_rect.height(),
                self.border_radius, self.border_radius
            )
            painter.fillPath(shadow_path, shadow_color)
        
        # Draw background
        path = QPainterPath()
        content_rect = self.rect().adjusted(0, 0, -4, -4)  # Account for shadow space
        path.addRoundedRect(
            content_rect.x(), content_rect.y(),
            content_rect.width(), content_rect.height(),
            self.border_radius, self.border_radius
        )
        
        painter.fillPath(path, self.bg_color)
        
        # Draw border
        from PyQt5.QtGui import QPen
        painter.setPen(QPen(self.border_color, 1))
        painter.drawPath(path)
        
        # Draw text
        painter.setPen(self.text_color)
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        
        painter.drawText(content_rect, Qt.AlignCenter, self._text)


class TooltipMixin:
    """Mixin to add themed tooltip functionality to any widget.
    
    Usage:
        class MyWidget(QWidget, TooltipMixin):
            def __init__(self):
                super().__init__()
                self.init_tooltip()
                
            def some_hover_method(self):
                self.show_tooltip("My tooltip text", QCursor.pos())
    """
    
    def init_tooltip(self):
        """Initialize tooltip system. Call in widget __init__."""
        self._tooltip = ThemedTooltip(self.window() if hasattr(self, 'window') else None)
        self._tooltip_enabled = True
    
    def show_tooltip(self, text: str, pos: QPoint = None, delay: int = None):
        """Show themed tooltip.
        
        Args:
            text: Tooltip text to display
            pos: Global position (uses cursor if None)
            delay: Delay in ms before showing (uses default if None)
        """
        if not self._tooltip_enabled or not hasattr(self, '_tooltip'):
            return
        
        if pos is None:
            from PyQt5.QtGui import QCursor
            pos = QCursor.pos()
        
        self._tooltip.setText(text)
        self._tooltip.showAt(pos, delay)
    
    def hide_tooltip(self, delay: int = None):
        """Hide themed tooltip.
        
        Args:
            delay: Delay in ms before hiding (uses default if None)
        """
        if hasattr(self, '_tooltip'):
            self._tooltip.hideTooltip(delay)
    
    def set_tooltip_enabled(self, enabled: bool):
        """Enable or disable tooltips."""
        self._tooltip_enabled = enabled
        if not enabled and hasattr(self, '_tooltip'):
            self._tooltip.hideTooltip(delay=0)
