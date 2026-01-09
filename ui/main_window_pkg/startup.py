from PyQt5.QtCore import QTimer

class StartupController:
    """Handle staged startup initialization and overlay updates."""

    def __init__(self, window):
        self.window = window
        self._overlay = None
        self._stage_index = 0
        self._stages = []

    def begin(self):
        """Show the startup overlay and run staged initialization."""
        from ui.startup_overlay import StartupOverlay

        # Parent overlay to player panel so it only occupies left side
        self._overlay = StartupOverlay(self.window.player_panel)
        self._overlay.start()
        self._stage_index = 0
        self._stages = [
            ("Initializing audio converter", self.window._init_converter),
            ("Setting up file watcher", self.window._init_file_watcher),
            ("Creating managers", self.window._init_managers),
            ("Registering shortcuts", self.window._init_shortcuts),
            ("Preparing audio analyzer", self.window._init_audio_analyzer_deferred),
            ("Starting update checker", self.window._init_updater_deferred),
        ]
        self._perform_next_stage()

    def _perform_next_stage(self):
        total = len(self._stages)
        if self._stage_index < total:
            desc, func = self._stages[self._stage_index]
            percent = int((self._stage_index / total) * 100)
            if self._overlay:
                self._overlay.update_progress(percent, desc)
            func()
            self._stage_index += 1
            QTimer.singleShot(10, self._perform_next_stage)
        else:
            if self._overlay:
                self._overlay.update_progress(100, "Ready")
                QTimer.singleShot(300, self._overlay.complete)
