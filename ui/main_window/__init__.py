"""Main window helpers and controllers."""

from .startup import StartupController
from .visualizer_host import VisualizerHost
from .library_controller import LibraryController

# Expose the main window class even though this package name collides with
# the legacy ui/main_window.py module file. We load that file explicitly by
# path under a unique module name to avoid the import shadowing caused by this
# package directory.
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_main_window_path = Path(__file__).resolve().parent.parent / "main_window.py"
_spec = spec_from_file_location("ui.main_window_window", _main_window_path)
_module = module_from_spec(_spec)
if _spec and _spec.loader:
    _spec.loader.exec_module(_module)
    SCDToolkit = _module.SCDToolkit
else:
    raise ImportError(f"Unable to load main window module at {_main_window_path}")
