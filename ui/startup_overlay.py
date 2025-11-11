"""Compact startup initialization panel shown in player area without blocking input."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty


class AnimatedProgressBar(QProgressBar):
    """Progress bar with smooth animated transitions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_value = 0
        self._animation = None
    
    @pyqtProperty(int)
    def animatedValue(self):
        return self._current_value
    
    @animatedValue.setter
    def animatedValue(self, value):
        self._current_value = value
        self.setValue(value)
    
    def setValueAnimated(self, target_value):
        """Animate smoothly to the target value."""
        if self._animation:
            self._animation.stop()
        
        self._animation = QPropertyAnimation(self, b"animatedValue")
        self._animation.setDuration(400)  # 400ms smooth transition
        self._animation.setStartValue(self._current_value)
        self._animation.setEndValue(target_value)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.start()


class StartupOverlay(QWidget):
    """Non-blocking compact panel for staged initialization.

    Appears inside the left player panel and allows user interaction with the rest
    of the window while initialization continues.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        # Light translucency for rounded panel shadow softness
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._done = False

        # Outer layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)

        # Fixed dimensions
        self.setFixedHeight(110)
        self.setFixedWidth(430)  # Match player panel inner width

        # Container panel
        self.panel = QWidget(self)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        self.panel.setStyleSheet(
            """
            QWidget {
                background-color: rgba(30, 30, 30, 205);
                border: 1px solid #444;
                border-radius: 10px;
            }
            QLabel { color: #ffffff; }
            QProgressBar {
                background: #1d1d1d;
                border: 1px solid #333;
                border-radius: 5px;
                height: 14px;
                text-align: center;
                color: #ddd;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #1e7ccc;
                border-radius: 5px;
            }
            """
        )

        self.title_label = QLabel("Initializing…")
        self.title_label.setStyleSheet("font-size:15px;font-weight:bold;")
        panel_layout.addWidget(self.title_label)

        self.detail_label = QLabel("Starting…")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size:12px;color:#bbbbbb;")
        panel_layout.addWidget(self.detail_label)

        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        panel_layout.addWidget(self.progress_bar)

        layout.addWidget(self.panel)

    def start(self):
        # Position directly below the seek slider (after file info)
        if self.parent():
            # Find the seek slider to position below it
            from ui.widgets import LoopSlider
            seek_slider = None
            for child in self.parent().children():
                if isinstance(child, LoopSlider):
                    seek_slider = child
                    break
            if seek_slider:
                # Position below seek slider, aligned to left
                y_pos = seek_slider.y() + seek_slider.height() + 8
                self.move(10, y_pos)
            else:
                # Fallback positioning
                self.move(10, 80)
        self.show()
        self.raise_()

    def update_progress(self, percent: int, message: str):
        if self._done:
            return
        self.progress_bar.setValueAnimated(percent)
        self.detail_label.setText(message)

    def complete(self):
        if self._done:
            return
        self._done = True
        self.detail_label.setText("Finished.")
        self.progress_bar.setValue(100)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.finished.connect(self._final_hide)
        anim.start()
        # Keep reference
        self._fade_anim = anim

    def _final_hide(self):
        self.hide()
        QTimer.singleShot(300, self.deleteLater)

    def reposition(self):
        if self.parent() and not self._done:
            # Find seek slider and reposition below it
            from ui.widgets import LoopSlider
            seek_slider = None
            for child in self.parent().children():
                if isinstance(child, LoopSlider):
                    seek_slider = child
                    break
            if seek_slider:
                y_pos = seek_slider.y() + seek_slider.height() + 8
                self.move(10, y_pos)

