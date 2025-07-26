# Custom UI widgets for SCD Player
from .core_widgets import ScrollingLabel, create_icon, create_app_icon, SplashScreen
from .timeline_widget import PreciseTimelineWidget
from .waveform_widget import WaveformWidget
from .metadata_reader import LoopMetadataReader

# Re-export for backward compatibility
__all__ = [
    'ScrollingLabel',
    'create_icon',
    'create_app_icon',
    'SplashScreen',
    'PreciseTimelineWidget',
    'WaveformWidget',
    'LoopMetadataReader'
]
