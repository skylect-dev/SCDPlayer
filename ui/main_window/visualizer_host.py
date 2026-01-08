from PyQt5.QtCore import QTimer, QObject, QEvent

class VisualizerHost(QObject):
    """Manage creation and positioning of the visualizer widget."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.visualizer = None
        self._installed_filters = False

    def create(self):
        """Create and attach the visualizer to the player panel."""
        if not hasattr(self.window, "player_panel"):
            return

        from ui.visualizer import VisualizerWidget

        self.visualizer = VisualizerWidget(self.window.player_panel)
        # Allow the visualizer to shrink when the window is short
        self.visualizer.setMinimumHeight(150)
        self.visualizer.visualizer_changed.connect(self.window.on_visualizer_changed)
        self.visualizer.show()

        # Position after layout settles
        QTimer.singleShot(10, self._position)

        # Install event filters once to track resizes without monkey patching
        if not self._installed_filters:
            self.window.installEventFilter(self)
            self.window.player_panel.installEventFilter(self)
            self._installed_filters = True

        # Connect to audio analyzer if ready
        if hasattr(self.window, "audio_analyzer") and self.window.audio_analyzer:
            self.visualizer.set_audio_callback(self.window.get_visualizer_audio_data)

    def _position(self):
        if not self.visualizer:
            return
        rect = self.window.player_panel.contentsRect()
        parent_height = rect.height()
        parent_width = rect.width()

        # Size to fit available height while respecting a sensible minimum
        desired_height = min(parent_height, max(150, self.visualizer.sizeHint().height()))

        # Stick to the bottom of the player panel; align left to contents rect
        y_pos = rect.bottom() - desired_height + 1  # +1 because bottom is inclusive
        self.visualizer.setGeometry(rect.left(), max(rect.top(), y_pos), parent_width, desired_height)
        self.visualizer.raise_()

    def _on_player_panel_resize(self, event):
        self._position()
        overlay = getattr(self.window, "_startup_overlay", None)
        if overlay and overlay.isVisible():
            overlay.reposition()

    def on_window_resize(self):
        """Adjust position when the main window resizes."""
        self._position()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and obj in (self.window, self.window.player_panel):
            self._position()
        return super().eventFilter(obj, event)
