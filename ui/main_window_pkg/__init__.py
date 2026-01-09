"""Refactored main-window components.

This package intentionally does NOT expose the application main window class.
The main window lives in the legacy module [ui/main_window.py](ui/main_window.py).
"""

from .library_controller import LibraryController
from .startup import StartupController
from .visualizer_host import VisualizerHost
