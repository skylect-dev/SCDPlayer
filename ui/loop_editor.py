"""Refactored Loop Point Editor Dialog for SCDPlayer"""
import os
import tempfile
import time
import numpy as np
import soundfile as sf
from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QSlider, QSpinBox, QGroupBox, QCheckBox, QMessageBox, QFileDialog, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut
from ui.dialogs import apply_title_bar_theming, show_themed_message
from .widgets import ScrollingLabel, PreciseTimelineWidget, WaveformWidget, LoopMetadataReader
from core.loop_manager import LoopPointManager
from utils.helpers import format_time


class LoopPointEditor(QDialog):
    """Refactored dialog for editing loop points in audio files"""
    
    def __init__(self, parent=None, file_path: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Loop Point Editor")
        self.setModal(True)
        self.resize(800, 700)
        
        # Ensure proper widget stacking and tooltip rendering
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        
        # Set window flags to ensure proper tooltip layering
        flags = self.windowFlags()
        flags |= Qt.WindowMaximizeButtonHint
        flags |= Qt.WindowMinimizeButtonHint
        self.setWindowFlags(flags)
        
        # Core components
        self.file_path = file_path
        self.temp_files = []
        self.loop_manager = LoopPointManager()
        self.metadata_reader = LoopMetadataReader(self.loop_manager)
        
        # Audio data
        self.waveform_data: Optional[np.ndarray] = None
        self.sample_rate: int = 44100
        self.temp_wav_path: Optional[str] = None
        
        # Media player for playback
        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.stateChanged.connect(self._on_state_changed)
        
        # Playback state
        self.is_loop_testing = False
        self.loop_testing_active = False  # Visual state for UI feedback
        self.loop_timer = QTimer()
        self.loop_timer.timeout.connect(self._check_loop_position)
        
        # High-frequency position update timer for smooth visual updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position_display)
        self.position_timer.setInterval(16)  # ~60 FPS updates
        
        self._setup_ui()
        self._setup_shortcuts()
        apply_title_bar_theming(self)
        
        # Ensure dialog is properly displayed with correct layering
        self.raise_()
        self.activateWindow()
        
        if file_path:
            self.load_audio_file(file_path)
    
    def closeEvent(self, event):
        """Clean up on close"""
        self._cleanup_temp_files()
        self.player.stop()
        self.loop_timer.stop()
        self.position_timer.stop()
        super().closeEvent(event)
    
    def _setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # File information
        layout.addWidget(self._create_file_info_group())
        
        # Waveform display
        layout.addWidget(self._create_waveform_group())
        
        # Timeline with draggable markers
        layout.addWidget(self._create_timeline_group())
        
        # Playback controls
        layout.addWidget(self._create_playback_group())
        
        # Loop point controls
        layout.addWidget(self._create_loop_controls_group())
        
        # Export options
        layout.addWidget(self._create_export_group())
        
        # Action buttons
        layout.addLayout(self._create_button_layout())
        
        self.setLayout(layout)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # S key - Set loop start to current playback position
        self.shortcut_set_start = QShortcut(QKeySequence("S"), self)
        self.shortcut_set_start.activated.connect(self._set_start_to_current_position)
        
        # E key - Set loop end to current playback position  
        self.shortcut_set_end = QShortcut(QKeySequence("E"), self)
        self.shortcut_set_end.activated.connect(self._set_end_to_current_position)
        
        # Enable fine control with Ctrl modifier for spinboxes
        self.start_sample_spin.installEventFilter(self)
        self.end_sample_spin.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Handle events for fine control with Ctrl key"""
        if event.type() == event.KeyPress:
            if event.modifiers() & Qt.ControlModifier:
                if obj in [self.start_sample_spin, self.end_sample_spin]:
                    # Enable single-step mode with Ctrl
                    old_step = obj.singleStep()
                    obj.setSingleStep(1)
                    # Let the event process normally
                    result = super().eventFilter(obj, event)
                    obj.setSingleStep(old_step)
                    return result
        return super().eventFilter(obj, event)
    
    def _set_start_to_current_position(self):
        """Set loop start to current playback position"""
        if self.player.state() == QMediaPlayer.PlayingState:
            # Use actual playback position when playing
            current_ms = self.player.position()
            current_sample = int((current_ms / 1000.0) * self.sample_rate)
        else:
            # Use timeline position when paused/stopped
            current_sample = self.timeline_widget.current_position
        
        self.start_sample_spin.setValue(current_sample)
    
    def _set_end_to_current_position(self):
        """Set loop end to current playback position"""
        if self.player.state() == QMediaPlayer.PlayingState:
            # Use actual playback position when playing
            current_ms = self.player.position()
            current_sample = int((current_ms / 1000.0) * self.sample_rate)
        else:
            # Use timeline position when paused/stopped
            current_sample = self.timeline_widget.current_position
            
        self.end_sample_spin.setValue(current_sample)
    
    def _create_file_info_group(self) -> QGroupBox:
        """Create file information group"""
        group = QGroupBox("File Information")
        layout = QVBoxLayout()
        
        self.file_label = QLabel("No file loaded")
        self.info_label = QLabel("")
        
        layout.addWidget(self.file_label)
        layout.addWidget(self.info_label)
        group.setLayout(layout)
        
        return group
    
    def _create_waveform_group(self) -> QGroupBox:
        """Create waveform display group"""
        group = QGroupBox("Waveform & Loop Points")
        layout = QVBoxLayout()
        
        self.waveform_widget = WaveformWidget()
        self.waveform_widget.positionClicked.connect(self._on_timeline_position_changed)
        self.waveform_widget.positionChanged.connect(self._on_timeline_position_changed)
        layout.addWidget(self.waveform_widget)
        
        group.setLayout(layout)
        return group
    
    def _create_timeline_group(self) -> QGroupBox:
        """Create timeline with draggable markers group"""
        group = QGroupBox("Timeline")
        layout = QVBoxLayout()
        
        self.timeline_widget = PreciseTimelineWidget()
        self.timeline_widget.positionChanged.connect(self._on_timeline_position_changed)
        self.timeline_widget.loopStartChanged.connect(self._on_timeline_start_changed)
        self.timeline_widget.loopEndChanged.connect(self._on_timeline_end_changed)
        layout.addWidget(self.timeline_widget)
        
        group.setLayout(layout)
        return group
    
    def _create_playback_group(self) -> QGroupBox:
        """Create playback controls group"""
        group = QGroupBox("Playback Controls")
        layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.clicked.connect(self._toggle_playback)
        layout.addWidget(self.play_pause_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_playback)
        layout.addWidget(self.stop_btn)
        
        self.loop_test_btn = QPushButton("Test Loop")
        self.loop_test_btn.setCheckable(True)  # Make it a toggle button
        self.loop_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 2px solid #666;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:checked {
                background-color: #2060c0;
                border-color: #4080ff;
                color: white;
            }
        """)
        self.loop_test_btn.clicked.connect(self._toggle_loop_testing)
        self.loop_test_btn.setEnabled(False)
        layout.addWidget(self.loop_test_btn)
        
        layout.addStretch()
        
        self.position_label = QLabel("0:00 / 0:00")
        layout.addWidget(self.position_label)
        
        group.setLayout(layout)
        return group
    
    def _create_loop_controls_group(self) -> QGroupBox:
        """Create loop point controls group"""
        group = QGroupBox("Loop Point Controls")
        layout = QVBoxLayout()
        
        # Add tip about hotkeys
        tip_label = QLabel("Tip: Use S to set start and E to set end at current playback position\nHold Ctrl while dragging timeline markers for fine precision control")
        tip_label.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        layout.addWidget(tip_label)
        
        # Start point
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Loop Start:"))
        
        self.start_sample_spin = QSpinBox()
        self.start_sample_spin.setMaximum(999999999)
        self.start_sample_spin.valueChanged.connect(self._on_start_changed)
        start_layout.addWidget(self.start_sample_spin)
        start_layout.addWidget(QLabel("samples"))
        
        self.start_time_label = QLabel("(0.000s)")
        start_layout.addWidget(self.start_time_label)
        start_layout.addStretch()
        
        layout.addLayout(start_layout)
        
        # End point
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("Loop End:"))
        
        self.end_sample_spin = QSpinBox()
        self.end_sample_spin.setMaximum(999999999)
        self.end_sample_spin.valueChanged.connect(self._on_end_changed)
        end_layout.addWidget(self.end_sample_spin)
        end_layout.addWidget(QLabel("samples"))
        
        self.end_time_label = QLabel("(0.000s)")
        end_layout.addWidget(self.end_time_label)
        end_layout.addStretch()
        
        layout.addLayout(end_layout)
        
        # Quick actions
        actions_layout = QHBoxLayout()
        
        self.detect_loop_btn = QPushButton("Auto-Detect Loop")
        self.detect_loop_btn.clicked.connect(self._auto_detect_loop)
        self.detect_loop_btn.setEnabled(False)
        actions_layout.addWidget(self.detect_loop_btn)
        
        self.clear_loop_btn = QPushButton("Clear Loop Points")
        self.clear_loop_btn.clicked.connect(self._clear_loop_points)
        actions_layout.addWidget(self.clear_loop_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_export_group(self) -> QGroupBox:
        """Create export options group"""
        group = QGroupBox("Export Options")
        layout = QVBoxLayout()
        
        self.trim_after_loop_cb = QCheckBox("Trim audio after loop end point")
        self.trim_after_loop_cb.setToolTip("Remove all audio after the loop end point")
        layout.addWidget(self.trim_after_loop_cb)
        
        group.setLayout(layout)
        return group
    
    def _create_button_layout(self) -> QHBoxLayout:
        """Create action buttons layout"""
        layout = QHBoxLayout()
        
        self.load_file_btn = QPushButton("Load Different File")
        self.load_file_btn.clicked.connect(self._load_file_dialog)
        layout.addWidget(self.load_file_btn)
        
        layout.addStretch()
        
        self.save_btn = QPushButton("Save Loop Points")
        self.save_btn.clicked.connect(self._save_loop_points)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
        
        return layout
    
    def _load_file_dialog(self):
        """Open file dialog to load audio file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Audio File", 
            "", 
            "Audio Files (*.wav *.mp3 *.scd *.ogg *.flac);;WAV Files (*.wav);;All Files (*.*)"
        )
        if file_path:
            self.load_audio_file(file_path)
    
    def load_audio_file(self, file_path: str):
        """Load and process audio file"""
        try:
            # Handle SCD files by converting to temp WAV
            actual_file_path = file_path
            if file_path.lower().endswith('.scd'):
                actual_file_path = self._convert_scd_to_temp_wav(file_path)
                if not actual_file_path:
                    show_themed_message(
                        self, QMessageBox.Warning, "Conversion Error",
                        "Failed to convert SCD file for editing."
                    )
                    return
            
            # Read audio data
            data, sample_rate = sf.read(actual_file_path)
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)  # Convert to mono
            
            # Update internal state
            self.waveform_data = data
            self.sample_rate = sample_rate
            self.file_path = file_path
            self.loop_manager.sample_rate = sample_rate
            self.loop_manager.total_samples = len(data)
            
            # Update UI
            self._update_file_info(file_path, data, sample_rate)
            self._update_controls_for_new_file(data)
            self._load_existing_metadata(file_path)
            
        except ImportError:
            show_themed_message(
                self, QMessageBox.Critical, "Missing Dependency",
                "The soundfile library is required.\nPlease install it with: pip install soundfile"
            )
        except Exception as e:
            show_themed_message(
                self, QMessageBox.Critical, "File Load Error",
                f"Failed to load audio file:\n{str(e)}"
            )
    
    def _convert_scd_to_temp_wav(self, scd_path: str) -> Optional[str]:
        """Convert SCD to temporary WAV file"""
        try:
            from core.converter import AudioConverter
            
            temp_dir = tempfile.gettempdir()
            temp_name = f"scd_loop_temp_{os.getpid()}_{int(time.time())}.wav"
            temp_path = os.path.join(temp_dir, temp_name)
            
            converter = AudioConverter()
            success = converter.convert_scd_to_wav(scd_path, temp_path)
            
            if success and os.path.exists(temp_path):
                self.temp_files.append(temp_path)
                self.temp_wav_path = temp_path
                return temp_path
            
        except Exception as e:
            print(f"Error converting SCD: {e}")
        
        return None
    
    def _update_file_info(self, file_path: str, data: np.ndarray, sample_rate: int):
        """Update file information display"""
        filename = os.path.basename(file_path)
        self.file_label.setText(f"File: {filename}")
        
        duration = len(data) / sample_rate
        self.info_label.setText(
            f"Duration: {format_time(duration * 1000)} | "
            f"Sample Rate: {sample_rate} Hz | "
            f"Samples: {len(data):,}"
        )
    
    def _update_controls_for_new_file(self, data: np.ndarray):
        """Update controls for newly loaded file"""
        # Update spinboxes
        self.start_sample_spin.setMaximum(len(data))
        self.end_sample_spin.setMaximum(len(data))
        self.end_sample_spin.setValue(len(data))
        
        # Update timeline
        self.timeline_widget.set_audio_info(len(data), self.sample_rate)
        
        # Update waveform
        self.waveform_widget.set_waveform_data(data, self.sample_rate)
        self.waveform_widget.set_loop_points(0, len(data))
        
        # Enable controls
        self.detect_loop_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
    
    def _load_existing_metadata(self, file_path: str):
        """Load existing loop metadata"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Read metadata for any file type
        metadata = self.metadata_reader.read_metadata(file_path)
        
        if metadata.get('has_loop', False):
            # Set loop points in the loop manager
            loop_start = metadata.get('loop_start', 0)
            loop_end = metadata.get('loop_end', 0)
            success = self.loop_manager.set_loop_points(loop_start, loop_end)
        else:
            success = False
        
        if success and self.loop_manager.current_loop:
            self._apply_loaded_loop_points()
    
    def _apply_loaded_loop_points(self):
        """Apply loaded loop points to UI"""
        loop = self.loop_manager.current_loop
        if not loop:
            return
        
        # Temporarily disconnect signals
        self.start_sample_spin.valueChanged.disconnect()
        self.end_sample_spin.valueChanged.disconnect()
        
        # Set values
        self.start_sample_spin.setValue(loop.start_sample)
        self.end_sample_spin.setValue(loop.end_sample)
        
        # Reconnect signals
        self.start_sample_spin.valueChanged.connect(self._on_start_changed)
        self.end_sample_spin.valueChanged.connect(self._on_end_changed)
        
        # Update displays
        self.waveform_widget.set_loop_points(loop.start_sample, loop.end_sample)
        self.timeline_widget.set_loop_points(loop.start_sample, loop.end_sample)
        self._update_time_labels()
        self._update_loop_test_button()
        
        print(f"Debug: Applied loop points - start: {loop.start_sample}, end: {loop.end_sample}")
    
    def _on_start_changed(self, value: int):
        """Handle start sample change"""
        self.loop_manager.set_loop_points(value, self.end_sample_spin.value())
        self.waveform_widget.set_loop_points(value, self.end_sample_spin.value())
        self.timeline_widget.set_loop_points(value, self.end_sample_spin.value())
        self._update_time_labels()
        self._update_loop_test_button()
    
    def _on_end_changed(self, value: int):
        """Handle end sample change"""
        self.loop_manager.set_loop_points(self.start_sample_spin.value(), value)
        self.waveform_widget.set_loop_points(self.start_sample_spin.value(), value)
        self.timeline_widget.set_loop_points(self.start_sample_spin.value(), value)
        self._update_time_labels()
        self._update_loop_test_button()
    
    def _update_time_labels(self):
        """Update time labels for loop points"""
        if self.sample_rate > 0:
            start_time = f"({self.start_sample_spin.value() / self.sample_rate:.3f}s)"
            end_time = f"({self.end_sample_spin.value() / self.sample_rate:.3f}s)"
            self.start_time_label.setText(start_time)
            self.end_time_label.setText(end_time)
    
    def _update_loop_test_button(self):
        """Update loop test button state"""
        has_valid_loop = (self.loop_manager.current_loop is not None and 
                         self.loop_manager.current_loop.start_sample < self.loop_manager.current_loop.end_sample)
        self.loop_test_btn.setEnabled(has_valid_loop)
    
    def _on_timeline_position_changed(self, sample: int):
        """Handle timeline position change with loop testing support"""
        position_ms = int((sample / self.sample_rate) * 1000) if self.sample_rate > 0 else 0
        
        if self.is_loop_testing and self.loop_manager.current_loop:
            # During loop testing, constrain movement to loop region
            loop_start = self.loop_manager.current_loop.start_sample
            loop_end = self.loop_manager.current_loop.end_sample
            
            # Only allow seeking within the loop region
            if loop_start <= sample <= loop_end:
                self.player.setPosition(position_ms)
        else:
            # Normal playback - allow seeking anywhere
            self.player.setPosition(position_ms)
    
    def _on_timeline_start_changed(self, sample: int):
        """Handle timeline loop start change"""
        self.start_sample_spin.setValue(sample)
    
    def _on_timeline_end_changed(self, sample: int):
        """Handle timeline loop end change"""
        self.end_sample_spin.setValue(sample)
    
    def _toggle_playback(self):
        """Toggle play/pause with loop testing awareness"""
        if not self.loop_testing_active:
            # Normal playback mode
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.pause()
            else:
                self._start_normal_playback()
        else:
            # Loop testing mode - toggle playback within loop
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.pause()
            else:
                # Resume loop testing
                self.player.play()
    
    def _start_normal_playback(self):
        """Start normal (non-loop) playback"""
        playback_file = self._get_playback_file()
        if not playback_file:
            return
        
        # Disable loop testing if it was active
        if self.loop_testing_active:
            self.loop_testing_active = False
            self.loop_test_btn.setChecked(False)
            self.loop_test_btn.setText("Test Loop")
            self.timeline_widget.set_loop_testing_active(False)
            self.waveform_widget.set_loop_testing_active(False)
        
        self.is_loop_testing = False
        self.loop_timer.stop()
        
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(playback_file)))
        self.player.play()
    
    def _stop_playback(self):
        """Stop all playback and reset loop testing"""
        self.player.stop()
        
        # Reset loop testing state
        if self.loop_testing_active:
            self.loop_testing_active = False
            self.loop_test_btn.setChecked(False)
            self.loop_test_btn.setText("Test Loop")
            self.timeline_widget.set_loop_testing_active(False)
            self.waveform_widget.set_loop_testing_active(False)
        
        self.is_loop_testing = False
        self.loop_timer.stop()
        self.waveform_widget.set_current_position(0)
        self.timeline_widget.set_current_position(0)
    
    def _toggle_loop_testing(self):
        """Toggle loop testing mode with visual feedback"""
        if not self.loop_manager.current_loop:
            return
        
        playback_file = self._get_playback_file()
        if not playback_file:
            return
        
        self.loop_testing_active = not self.loop_testing_active
        self.is_loop_testing = self.loop_testing_active
        
        # Update UI visual feedback
        self.timeline_widget.set_loop_testing_active(self.loop_testing_active)
        self.waveform_widget.set_loop_testing_active(self.loop_testing_active)
        
        if self.loop_testing_active:
            # Start loop testing
            self.loop_test_btn.setText("Stop Loop Test")
            self._start_loop_testing(playback_file)
        else:
            # Stop loop testing
            self.loop_test_btn.setText("Test Loop")
            self._stop_loop_testing()
    
    def _start_loop_testing(self, playback_file):
        """Start loop testing playback"""
        # Enable loop testing mode
        self.loop_timer.start(10)  # Check every 10ms for high precision
        
        # Calculate loop positions in milliseconds with high precision
        loop_start_ms = int((self.loop_manager.current_loop.start_sample / self.sample_rate) * 1000)
        
        # Start playback from loop start
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(playback_file)))
        self.player.setPosition(loop_start_ms)
        self.player.play()
        
        print(f"Debug: Starting loop test from {loop_start_ms}ms")
    
    def _stop_loop_testing(self):
        """Stop loop testing and return to normal mode"""
        self.loop_timer.stop()
        self.player.pause()
        
        # Reset position to beginning for normal playback
        self.player.setPosition(0)
    
    def _test_loop_playback(self):
        """Legacy method - redirect to toggle for compatibility"""
        if not self.loop_testing_active:
            self.loop_test_btn.setChecked(True)
            self._toggle_loop_testing()
    
    def _check_loop_position(self):
        """Check if we need to loop back to start"""
        if not self.is_loop_testing or not self.loop_manager.current_loop:
            return
        
        current_ms = self.player.position()
        loop_end_ms = int((self.loop_manager.current_loop.end_sample / self.sample_rate) * 1000)
        loop_start_ms = int((self.loop_manager.current_loop.start_sample / self.sample_rate) * 1000)
        
        # Trigger loop slightly before the actual end to account for playback latency
        # Use a 20ms buffer to ensure we don't overshoot
        loop_trigger_ms = loop_end_ms - 20
        
        # If we've reached the trigger point, jump back to start
        if current_ms >= loop_trigger_ms:
            self.player.setPosition(loop_start_ms)
            print(f"Debug: Looping back to {loop_start_ms}ms (triggered at {current_ms}ms, end at {loop_end_ms}ms)")
    
    def _get_playback_file(self) -> Optional[str]:
        """Get appropriate file for playback"""
        if self.temp_wav_path and os.path.exists(self.temp_wav_path):
            return self.temp_wav_path
        elif self.file_path and os.path.exists(self.file_path):
            return self.file_path
        else:
            show_themed_message(
                self, QMessageBox.Warning, "No Audio",
                "No audio file available for playback."
            )
            return None
    
    def _update_position_display(self):
        """High-frequency position display update for smooth visual feedback"""
        if self.player.state() == QMediaPlayer.PlayingState and self.sample_rate > 0 and self.waveform_data is not None:
            position = self.player.position()
            sample_position = int((position / 1000.0) * self.sample_rate)
            sample_position = min(sample_position, len(self.waveform_data) - 1)
            
            # Update visual displays only (no label updates to avoid flicker)
            self.waveform_widget.set_current_position(sample_position)
            self.timeline_widget.set_current_position(sample_position)
    
    def _on_position_changed(self, position):
        """Handle playback position changes (lower frequency, includes label updates)"""
        if self.sample_rate > 0 and self.waveform_data is not None:
            # Calculate sample position
            sample_position = int((position / 1000.0) * self.sample_rate)
            sample_position = min(sample_position, len(self.waveform_data) - 1)
            
            # Update position label (only here to avoid too frequent text updates)
            current_time = format_time(position / 1000.0)
            total_time = format_time(self.player.duration() / 1000.0) if self.player.duration() > 0 else "0:00"
            self.position_label.setText(f"{current_time} / {total_time}")
            
            # Visual updates are now handled by _update_position_display for smoothness
    
    def _on_duration_changed(self, duration):
        """Handle duration changes"""
        # Duration changed - no specific action needed for timeline
    
    def _on_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("Pause")
            self.position_timer.start()  # Start high-frequency position updates
        else:
            self.play_pause_btn.setText("Play")
            self.position_timer.stop()  # Stop high-frequency updates when not playing
    
    def _auto_detect_loop(self):
        """Attempt to automatically detect loop points"""
        if self.waveform_data is None:
            show_themed_message(
                self, QMessageBox.Warning, "No Audio Data",
                "Please load an audio file first."
            )
            return
        
        # Simple auto-detection (can be enhanced)
        total_samples = len(self.waveform_data)
        suggested_start = int(total_samples * 0.1)  # 10% from start
        suggested_end = int(total_samples * 0.9)    # 90% of total
        
        self.start_sample_spin.setValue(suggested_start)
        self.end_sample_spin.setValue(suggested_end)
        
        show_themed_message(
            self, QMessageBox.Information, "Auto-Detection",
            f"Suggested loop points:\n"
            f"• Start: {suggested_start:,} samples\n"
            f"• End: {suggested_end:,} samples\n\n"
            f"Please adjust manually for best results."
        )
    
    def _clear_loop_points(self):
        """Clear all loop points"""
        self.start_sample_spin.setValue(0)
        self.end_sample_spin.setValue(self.loop_manager.total_samples)
        self.loop_manager.clear_loop_points()
    
    def _save_loop_points(self):
        """Save loop points to original file"""
        if not self.file_path or not self.loop_manager.current_loop:
            return
        
        # Confirm overwrite
        reply = show_themed_message(
            self, QMessageBox.Question, "Save Loop Points",
            f"Save loop points to:\n{os.path.basename(self.file_path)}\n\n"
            f"This will modify the original file.\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Show progress dialog
            from PyQt5.QtWidgets import QProgressDialog
            progress = QProgressDialog("Saving loop points...", None, 0, 0, self)
            progress.setWindowTitle("Saving")
            progress.setModal(True)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            try:
                file_ext = os.path.splitext(self.file_path)[1].lower()
                
                if file_ext == '.wav':
                    success = self._save_wav_loop_points()
                elif file_ext == '.scd':
                    success = self._save_scd_loop_points()
                else:
                    success = self._save_other_format_loop_points()
                
                progress.close()
                
                if success:
                    show_themed_message(
                        self, QMessageBox.Information, "Success",
                        "Loop points saved successfully!"
                    )
                else:
                    show_themed_message(
                        self, QMessageBox.Warning, "Save Failed",
                        "Failed to save loop points."
                    )
                    
            except Exception as e:
                progress.close()
                show_themed_message(
                    self, QMessageBox.Critical, "Save Error",
                    f"Error saving loop points:\n{str(e)}"
                )
    
    def _save_wav_loop_points(self) -> bool:
        """Save loop points to WAV file"""
        try:
            return self.loop_manager.add_loop_metadata_to_wav(
                self.file_path, 
                trim_after_loop=self.trim_after_loop_cb.isChecked()
            )
        except Exception as e:
            print(f"Error saving WAV loop points: {e}")
            return False
    
    def _save_scd_loop_points(self) -> bool:
        """Save loop points to SCD file"""
        try:
            return self.loop_manager.save_scd_loop_metadata(
                self.file_path,
                trim_after_loop=self.trim_after_loop_cb.isChecked()
            )
        except Exception as e:
            print(f"Error saving SCD loop points: {e}")
            return False
    
    def _save_other_format_loop_points(self) -> bool:
        """Save loop points to other formats"""
        try:
            return self.loop_manager.save_other_format_loop_metadata(
                self.file_path,
                trim_after_loop=self.trim_after_loop_cb.isChecked()
            )
        except Exception as e:
            print(f"Error saving other format loop points: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        self.temp_files.clear()
        self.temp_wav_path = None
