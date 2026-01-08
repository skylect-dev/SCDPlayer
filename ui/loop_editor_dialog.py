import logging
import sys
import os
import wave
import struct
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from core.audio_analysis import AudioAnalyzer
from ui.loop_editor.dialogs import CustomVolumeDialog
from ui.styles import (
    BUTTON_APPLY_SCD,
    BUTTON_CANCEL_DANGER,
    BUTTON_CLEAR_DARK,
    BUTTON_PRIMARY_BLUE,
    BUTTON_SECONDARY_DARK,
    BUTTON_TOGGLE_LOOP,
    BUTTON_VOLUME_GREEN,
    BUTTON_VOLUME_RESET,
)
from ui.loop_editor.workers import LoudnessWorker, SaveWorker
from ui.loop_editor.waveform import TimelineWidget, WaveformWidget


class LoopEditorDialog(QDialog):
    """Professional loop editor dialog"""
    
    def __init__(self, loop_manager, parent=None):
        super().__init__(parent)
        self.loop_manager = loop_manager
        self.parent_window = parent
        
        # Track if volume has been adjusted
        self._volume_adjusted = False
        self._original_audio_data = None  # Keep copy of original for comparison
        
        # Temporary file management for volume adjustments
        self._temp_wav_path = None  # Path to temporary volume-adjusted WAV file
        self._original_wav_path = None  # Original WAV file path
        self._temp_file_created = False  # Track if we created a temp file
        
        # Pause main window audio if playing
        if hasattr(parent, 'player') and parent.player.state() == parent.player.PlayingState:
            parent.pause_audio()
            self.main_was_playing = True
        else:
            self.main_was_playing = False
        
        # Initialize media player for playback
        self.media_player = QMediaPlayer()
        self.media_player.positionChanged.connect(self.on_playback_position_changed)
        self.media_player.stateChanged.connect(self.on_playback_state_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)

        # Busy overlay for long operations
        self.busy_overlay = None
        self.busy_label = None
        self.busy_bar = None
        
        # Playback state
        self.is_loop_testing = False
        # Position update timer for ultra-smooth sample-based updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_sample_position)
        
        # Loop timer for checking loop boundaries
        self.loop_timer = QTimer()
        self.loop_timer.timeout.connect(self.check_loop_position)
        
        self.setup_ui()
        self.load_audio_data()
        # Set window title to file name if available
        file_path = getattr(self.loop_manager, "current_file_path", None)
        if file_path:
            self.setWindowTitle(f"{Path(file_path).name} - Loop Editor")
        else:
            self.setWindowTitle("Loop Editor")
        
    def setup_ui(self):
        """Setup the user interface"""
        # Window title is set in __init__ to file name
        self.setMinimumSize(800, 650)
        self.resize(1400, 800)
        
        # Enable maximize and minimize buttons
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        
        # Apply professional dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #ddd;
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ddd;
                border: none;
                background-color: transparent;
            }
            QSpinBox {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: white;
            }
            QSpinBox:focus {
                border-color: #4080ff;
            }
            QDoubleSpinBox {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: white;
            }
            QDoubleSpinBox:focus {
                border-color: #4080ff;
            }
            QRadioButton {
                color: #ddd;
                background-color: transparent;
            }
            QScrollBar:horizontal {
                background-color: #404040;
                height: 16px;
                border-radius: 8px;
            }
            QScrollBar::handle:horizontal {
                background-color: #666;
                border-radius: 8px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #777;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.setMaximumHeight(40)
        layout.addWidget(self.timeline)
        
        # Waveform with scrollbar
        waveform_container = QWidget()
        waveform_layout = QHBoxLayout(waveform_container)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        
        self.waveform = WaveformWidget()
        self.waveform.positionChanged.connect(self.on_position_changed)
        self.waveform.loopPointChanged.connect(self.on_loop_points_changed)
        self.waveform.trimPointChanged.connect(lambda s, e: self.update_trim_label())
        
        # Connect focus callback
        self.waveform.focus_callback = self.toggle_follow_mode
        
        # Connect follow callback for auto-follow behavior
        self.waveform.follow_callback = self.follow_playback_cursor
        
        # Add horizontal scrollbar
        self.waveform_scroll = QScrollBar(Qt.Horizontal)
        self.waveform_scroll.valueChanged.connect(self.on_scroll_changed)
        
        waveform_layout.addWidget(self.waveform)
        
        # Vertical layout for waveform and scrollbar
        waveform_with_scroll = QVBoxLayout()
        waveform_with_scroll.setContentsMargins(0, 0, 0, 0)
        waveform_with_scroll.addWidget(self.waveform)
        waveform_with_scroll.addWidget(self.waveform_scroll)
        
        waveform_scroll_widget = QWidget()
        waveform_scroll_widget.setLayout(waveform_with_scroll)
        layout.addWidget(waveform_scroll_widget)
        
        # Playback controls
        playback_group = QGroupBox("Playback Controls")
        playback_layout = QHBoxLayout(playback_group)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        self.play_btn.setStyleSheet(BUTTON_PRIMARY_BLUE)
        playback_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.stop_btn.setStyleSheet(BUTTON_SECONDARY_DARK)
        playback_layout.addWidget(self.stop_btn)
        
        self.loop_test_btn = QPushButton("Loop")
        self.loop_test_btn.setCheckable(True)
        self.loop_test_btn.clicked.connect(self.toggle_loop_mode)
        self.loop_test_btn.setStyleSheet(BUTTON_TOGGLE_LOOP)
        playback_layout.addWidget(self.loop_test_btn)
        
        playback_layout.addStretch()
        
        # Add volume control inline with playback controls
        from ui.volume_control import VolumeControl
        self.volume_control = VolumeControl()
        self.volume_control.setVolume(70)  # Default volume
        self.volume_control.volumeChanged.connect(self.on_volume_changed)
        playback_layout.addWidget(self.volume_control)
        playback_layout.addSpacing(10)
        
        self.position_label = QLabel("0:00 / 0:00")
        self.position_label.setStyleSheet("color: #ccc; font-family: monospace;")
        playback_layout.addWidget(self.position_label)
        
        layout.addWidget(playback_group)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Loop info group with better styling
        info_group = QGroupBox("Loop Point Controls")
        info_layout = QVBoxLayout(info_group)
        
        # Add helpful tip
        tip_label = QLabel(
            "Hotkeys:\n"
            "S: Set loop start at cursor\n"
            "E: Set loop end at cursor\n"
            "C: Clear loop points\n"
            "F: Toggle auto-follow cursor\n"
            "L: Toggle loop playback\n"
            "Space: Play/Pause\n"
            "Ctrl+drag: Fine marker control"
        )
        tip_label.setStyleSheet("color: #888; font-style: italic; padding: 5px; background-color: rgba(255, 255, 255, 0.05); border-radius: 3px;")
        tip_label.setWordWrap(True)
        info_layout.addWidget(tip_label)

        # Mode toggle
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_loop_radio = QRadioButton("Loop")
        self.mode_trim_radio = QRadioButton("Trim")
        self.mode_loop_radio.setChecked(True)
        self.mode_loop_radio.toggled.connect(lambda checked: self.on_mode_changed('loop' if checked else 'trim'))
        mode_layout.addWidget(self.mode_loop_radio)
        mode_layout.addWidget(self.mode_trim_radio)
        mode_layout.addStretch()
        info_layout.addLayout(mode_layout)

        # Trim info and actions
        trim_row = QHBoxLayout()
        self.trim_label = QLabel("Trim: full length")
        self.trim_label.setStyleSheet("color: #ccc;")
        trim_row.addWidget(self.trim_label)

        self.trim_apply_btn = QPushButton("Apply Trim")
        self.trim_apply_btn.clicked.connect(self.on_apply_trim)
        trim_row.addWidget(self.trim_apply_btn)

        self.trim_reset_btn = QPushButton("Reset Trim")
        self.trim_reset_btn.clicked.connect(self.on_reset_trim)
        trim_row.addWidget(self.trim_reset_btn)
        trim_row.addStretch()
        info_layout.addLayout(trim_row)
        
        # Start point controls
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Loop Start:"))
        
        self.start_spin = QSpinBox()
        self.start_spin.setMaximum(2147483647)
        self.start_spin.valueChanged.connect(self.on_loop_start_changed)
        self.start_spin.setStyleSheet("QSpinBox { padding: 4px; }")
        start_layout.addWidget(self.start_spin)
        start_layout.addWidget(QLabel("samples"))
        
        # Add seconds input for start point
        start_layout.addWidget(QLabel("or"))
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setMaximum(999999.999)
        self.start_time_spin.setDecimals(3)
        self.start_time_spin.setSingleStep(0.001)
        self.start_time_spin.valueChanged.connect(self.on_loop_start_time_changed)
        self.start_time_spin.setStyleSheet("QDoubleSpinBox { padding: 4px; }")
        start_layout.addWidget(self.start_time_spin)
        start_layout.addWidget(QLabel("seconds"))
        
        start_layout.addStretch()
        
        info_layout.addLayout(start_layout)
        
        # End point controls
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("Loop End:"))
        
        self.end_spin = QSpinBox()
        self.end_spin.setMaximum(2147483647)
        self.end_spin.valueChanged.connect(self.on_loop_end_changed)
        self.end_spin.setStyleSheet("QSpinBox { padding: 4px; }")
        end_layout.addWidget(self.end_spin)
        end_layout.addWidget(QLabel("samples"))
        
        # Add seconds input for end point
        end_layout.addWidget(QLabel("or"))
        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setMaximum(999999.999)
        self.end_time_spin.setDecimals(3)
        self.end_time_spin.setSingleStep(0.001)
        self.end_time_spin.valueChanged.connect(self.on_loop_end_time_changed)
        self.end_time_spin.setStyleSheet("QDoubleSpinBox { padding: 4px; }")
        end_layout.addWidget(self.end_time_spin)
        end_layout.addWidget(QLabel("seconds"))
        
        end_layout.addStretch()
        
        info_layout.addLayout(end_layout)
        
        # Duration display
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        self.duration_label = QLabel("0 samples")
        self.duration_label.setStyleSheet("font-weight: bold; color: #ddd;")
        duration_layout.addWidget(self.duration_label)
        duration_layout.addStretch()
        info_layout.addLayout(duration_layout)
        
        controls_layout.addWidget(info_group)
        
        # Audio Analysis Panel
        self.analysis_group = QGroupBox("Audio Analysis")
        self.analysis_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        analysis_layout = QVBoxLayout(self.analysis_group)
        
        # Analysis display area - make it expand with window
        self.analysis_text = QTextEdit()
        self.analysis_text.setMinimumHeight(150)
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.analysis_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: #ddd;
            }
        """)
        analysis_layout.addWidget(self.analysis_text)
        
        # Analysis button
        analyze_btn = QPushButton("Analyze Audio Levels")
        analyze_btn.clicked.connect(self.analyze_audio)
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover { background-color: #5a5a5a; }
            QPushButton:pressed { background-color: #3a3a3a; }
        """)
        analysis_layout.addWidget(analyze_btn)
        
        # Volume adjustment buttons
        volume_btn_layout = QHBoxLayout()
        
        self.adjust_volume_btn = QPushButton("Adjust Volume (-12 LUFS)")
        self.adjust_volume_btn.clicked.connect(self.adjust_volume_lufs)
        self.adjust_volume_btn.setToolTip("True loudness normalize to -12 LUFS / -1 dBTP (ffmpeg loudnorm)")

        self.increase_lufs_btn = QPushButton("Increase (+1 LUFS)")
        self.increase_lufs_btn.clicked.connect(lambda: self.adjust_volume_relative(+1.0))
        self.increase_lufs_btn.setToolTip("Raise loudness by about +1 LUFS (true loudnorm)")

        self.decrease_lufs_btn = QPushButton("Decrease (-1 LUFS)")
        self.decrease_lufs_btn.clicked.connect(lambda: self.adjust_volume_relative(-1.0))
        self.decrease_lufs_btn.setToolTip("Lower loudness by about -1 LUFS (true loudnorm)")
        
        self.reset_volume_btn = QPushButton("Reset Volume")
        self.reset_volume_btn.clicked.connect(self.reset_volume_adjustment)
        self.reset_volume_btn.setToolTip("Reset audio to original volume levels")
        self.reset_volume_btn.setEnabled(False)  # Only enabled after volume adjustment
        
        # Style the volume buttons
        self.adjust_volume_btn.setStyleSheet(BUTTON_VOLUME_GREEN)
        self.increase_lufs_btn.setStyleSheet(BUTTON_VOLUME_GREEN)
        self.decrease_lufs_btn.setStyleSheet(BUTTON_VOLUME_GREEN)
        self.reset_volume_btn.setStyleSheet(BUTTON_VOLUME_RESET)
        
        volume_btn_layout.addWidget(self.adjust_volume_btn)
        volume_btn_layout.addWidget(self.increase_lufs_btn)
        volume_btn_layout.addWidget(self.decrease_lufs_btn)
        volume_btn_layout.addWidget(self.reset_volume_btn)
        
        analysis_layout.addLayout(volume_btn_layout)
        
        # SCD Volume Float Editor
        scd_volume_layout = QHBoxLayout()
        
        scd_label = QLabel("SCD Volume Float:")
        scd_label.setStyleSheet("color: #aaa; font-size: 10px; font-weight: bold;")
        scd_label.setToolTip("Direct SCD header volume multiplier (typically 0.48-2.0)")
        
        self.scd_volume_spinbox = QDoubleSpinBox()
        self.scd_volume_spinbox.setRange(0.0, 3.0)
        self.scd_volume_spinbox.setSingleStep(0.1)
        self.scd_volume_spinbox.setDecimals(2)
        self.scd_volume_spinbox.setValue(1.2)
        self.scd_volume_spinbox.setFixedWidth(80)
        self.scd_volume_spinbox.setToolTip("Volume float at SCD header offset (table_ptr + 0x08)\nOfficial files: ~0.48, Recommended: 1.0-1.5")
        self.scd_volume_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
                color: #ddd;
                font-size: 11px;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #4a8a4a;
            }
        """)
        
        self.apply_scd_volume_btn = QPushButton("Apply Float")
        self.apply_scd_volume_btn.clicked.connect(self.apply_scd_volume_float)
        self.apply_scd_volume_btn.setToolTip("Patch the SCD file with this volume float value")
        self.apply_scd_volume_btn.setFixedWidth(90)
        
        self.apply_scd_volume_btn.setStyleSheet(BUTTON_APPLY_SCD)
        
        self.scd_volume_status = QLabel("")
        self.scd_volume_status.setStyleSheet("color: #888; font-size: 9px; font-style: italic;")
        
        scd_volume_layout.addWidget(scd_label)
        scd_volume_layout.addWidget(self.scd_volume_spinbox)
        scd_volume_layout.addWidget(self.apply_scd_volume_btn)
        scd_volume_layout.addWidget(self.scd_volume_status, 1)
        
        analysis_layout.addLayout(scd_volume_layout)
        
        # Initially disable volume buttons until audio is loaded
        self.adjust_volume_btn.setEnabled(False)
        self.increase_lufs_btn.setEnabled(False)
        self.decrease_lufs_btn.setEnabled(False)
        self.reset_volume_btn.setEnabled(False)
        self.scd_volume_spinbox.setEnabled(False)
        self.apply_scd_volume_btn.setEnabled(False)
        
        controls_layout.addWidget(self.analysis_group, 1)  # Give analysis group more space with stretch factor
        
        # Action buttons with professional styling
        button_group = QGroupBox("Actions")
        button_layout = QVBoxLayout(button_group)
        
        # Clear button
        self.clear_btn = QPushButton("Clear Loop Points (C)")
        self.clear_btn.clicked.connect(self.clear_loop_points)
        self.clear_btn.setStyleSheet(BUTTON_CLEAR_DARK)
        button_layout.addWidget(self.clear_btn)
        
        # Save button
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setStyleSheet(BUTTON_PRIMARY_BLUE)
        button_layout.addWidget(self.save_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_dialog)
        self.cancel_btn.setStyleSheet(BUTTON_CANCEL_DANGER)
        button_layout.addWidget(self.cancel_btn)
        
        controls_layout.addWidget(button_group)
        
        layout.addLayout(controls_layout)
        
        # Connect timeline to waveform and scrollbar
        self.waveform.scrollChanged = self.timeline.set_view_params
        self.waveform.zoomChanged = self.update_scrollbar_range

        # Build hidden overlay to block input during long-running work
        self._init_busy_overlay()

    def _init_busy_overlay(self):
        """Create a modal-style overlay to block input during background work"""
        self.busy_overlay = QWidget(self)
        self.busy_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self.busy_overlay.hide()

        layout = QVBoxLayout(self.busy_overlay)
        layout.setAlignment(Qt.AlignCenter)

        self.busy_label = QLabel("Working...")
        self.busy_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")

        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)  # Indeterminate
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(260)
        self.busy_bar.setStyleSheet("QProgressBar { border: 1px solid #666; border-radius: 4px; background: #333; } QProgressBar::chunk { background: #4a90e2; }")

        layout.addWidget(self.busy_label, 0, Qt.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.busy_bar, 0, Qt.AlignHCenter)

    def _show_busy(self, message: str = "Working..."):
        """Display the busy overlay with the given message"""
        if not self.busy_overlay:
            return
        self.busy_label.setText(message)
        self.busy_overlay.setGeometry(self.rect())
        self.busy_overlay.raise_()
        self.busy_overlay.show()

    def _hide_busy(self):
        """Hide the busy overlay"""
        if self.busy_overlay:
            self.busy_overlay.hide()

    def resizeEvent(self, event):
        """Keep overlay covering the dialog on resize"""
        super().resizeEvent(event)
        if self.busy_overlay and self.busy_overlay.isVisible():
            self.busy_overlay.setGeometry(self.rect())
        
    def closeEvent(self, event):
        """Clean up when dialog closes"""
        # Stop all playback and timers
        self.media_player.stop()
        self.position_timer.stop()
        self.loop_timer.stop()
        
        # Clean up temporary files to release all file handles
        self._cleanup_temp_files()
        
        # Resume main window audio if it was playing
        if self.main_was_playing and hasattr(self.parent_window, 'play_audio'):
            self.parent_window.play_audio()
        
        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        """Handle global keyboard shortcuts regardless of focus"""
        # Space: Play/Pause toggle
        if event.key() == Qt.Key_Space:
            self.toggle_playback()
            event.accept()
            return
            
        # S: Set loop start at current position
        elif event.key() == Qt.Key_S:
            if hasattr(self.waveform, 'current_position'):
                current_pos = self.waveform.current_position
                end = self.end_spin.value()
                if end <= current_pos:
                    file_info = self.loop_manager.get_file_info()
                    end = file_info.get('total_samples', 0)
                self.waveform.set_loop_points(current_pos, end)
                self.update_loop_info(current_pos, end)
            event.accept()
            return
            
        # E: Set loop end at current position  
        elif event.key() == Qt.Key_E:
            if hasattr(self.waveform, 'current_position'):
                current_pos = self.waveform.current_position
                start = self.start_spin.value()
                if start >= current_pos:
                    start = 0
                self.waveform.set_loop_points(start, current_pos)
                self.update_loop_info(start, current_pos)
            event.accept()
            return
            
        # C: Clear loop points
        elif event.key() == Qt.Key_C:
            self.clear_loop_points()
            event.accept()
            return
            
        # L: Toggle loop mode
        elif event.key() == Qt.Key_L:
            self.loop_test_btn.setChecked(not self.loop_test_btn.isChecked())
            self.toggle_loop_mode()
            event.accept()
            return
            
        # F: Toggle auto-follow cursor mode
        elif event.key() == Qt.Key_F:
            self.toggle_follow_mode()
            event.accept()
            return
        
        # Pass other keys to parent
        super().keyPressEvent(event)
        
    def load_audio_data(self):
        """Load audio data into the waveform widget"""
        if not self.loop_manager.get_wav_path():
            QMessageBox.warning(self, "Error", "No audio file loaded")
            return

        success = self.waveform.load_audio_data(self.loop_manager.get_wav_path())
        if not success:
            QMessageBox.warning(self, "Error", "Failed to load audio data")
            return

        # Store original audio data for volume change detection
        if self.waveform.audio_data is not None:
            self._original_audio_data = self.waveform.audio_data.copy()
            self._volume_adjusted = False

        # Set timeline info
        file_info = self.loop_manager.get_file_info()
        self.timeline.set_audio_info(file_info['sample_rate'], file_info['total_samples'])

        # Set current loop points or defaults
        start, end = self.loop_manager.get_loop_points()

        # If no loop points exist, set default end to track length
        if end == 0:
            file_info = self.loop_manager.get_file_info()
            end = file_info.get('total_samples', 0)

        self.waveform.set_loop_points(start, end)
        self.update_loop_info(start, end)

        # Initialize trim range to full length
        self.waveform.reset_trim_points()
        self.update_trim_label()

        # Automatically analyze audio levels when file loads
        self.analysis_text.setText("Analyzing audio levels...")
        QTimer.singleShot(100, self.analyze_audio)  # Delay slightly to let UI update

        # Update volume button states  
        self._update_volume_buttons_state()
        
        # Read and display current SCD volume float if this is an SCD file
        self._read_scd_volume_float()

        # Initialize scrollbar and zoom properly after widget is shown
        QTimer.singleShot(200, self._finalize_waveform_setup)

    def _finalize_waveform_setup(self):
        """Finalize waveform setup after UI is fully initialized"""
        # Ensure proper zoom initialization
        if hasattr(self.waveform, 'audio_data') and self.waveform.audio_data is not None:
            # Reset zoom to show full waveform with proper scaling
            total_samples = len(self.waveform.audio_data)
            widget_width = self.waveform.width()
            if widget_width > 0:
                # Set samples per pixel to show full track
                self.waveform.samples_per_pixel = max(1, total_samples / widget_width)
                self.waveform._scroll_position = 0
                self.waveform.update()
                
                # IMPORTANT: Update timeline with the correct initial parameters
                if hasattr(self.waveform, 'scrollChanged') and self.waveform.scrollChanged:
                    self.waveform.scrollChanged(
                        self.waveform._scroll_position, 
                        self.waveform.zoom_factor, 
                        self.waveform.samples_per_pixel
                    )
        
        # Initialize scrollbar with correct values
        self.update_scrollbar_range()
        
    def on_scroll_changed(self, value):
        """Handle scrollbar changes"""
        if hasattr(self.waveform, 'set_scroll_position'):
            # Mark this as programmatic scroll to prevent follow state reset
            self.waveform._programmatic_scroll = True
            self.waveform.set_scroll_position(value)
            if hasattr(self.waveform, '_programmatic_scroll'):
                delattr(self.waveform, '_programmatic_scroll')
        
    def update_scrollbar_range(self):
        """Update scrollbar range based on zoom level"""
        if hasattr(self.waveform, 'get_scroll_info'):
            scroll_info = self.waveform.get_scroll_info()
            self.waveform_scroll.setRange(0, int(scroll_info.get('max_scroll', 0)))
            self.waveform_scroll.setPageStep(int(scroll_info.get('page_step', 100)))
            self.waveform_scroll.setValue(int(scroll_info.get('current_scroll', 0)))
        
    def on_position_changed(self, position: int):
        """Handle playback position change from waveform clicks"""
        # Seek to the clicked position
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        position_ms = int((position / sample_rate) * 1000)
        
        # Seek the media player to this position
        self.media_player.setPosition(position_ms)
    
    def on_loop_points_changed(self, start: int, end: int):
        """Handle loop points change from waveform"""
        self.update_loop_info(start, end)
        
    def on_loop_start_changed(self, value: int):
        """Handle loop start change from spin box"""
        end = self.end_spin.value()
        if value < end:
            self.waveform.set_loop_points(value, end)
            self.update_duration_label(value, end)
            self.update_time_spinboxes()
    
    def on_loop_end_changed(self, value: int):
        """Handle loop end change from spin box"""
        start = self.start_spin.value()
        if value > start:
            self.waveform.set_loop_points(start, value)
            self.update_duration_label(start, value)
            self.update_time_spinboxes()
    
    def on_loop_start_time_changed(self, time_seconds: float):
        """Handle loop start time change from seconds spin box"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            sample_value = int(time_seconds * sample_rate)
            end = self.end_spin.value()
            if sample_value < end:
                self.start_spin.blockSignals(True)
                self.start_spin.setValue(sample_value)
                self.start_spin.blockSignals(False)
                self.waveform.set_loop_points(sample_value, end)
                self.update_duration_label(sample_value, end)
    
    def on_loop_end_time_changed(self, time_seconds: float):
        """Handle loop end time change from seconds spin box"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            sample_value = int(time_seconds * sample_rate)
            start = self.start_spin.value()
            if sample_value > start:
                self.end_spin.blockSignals(True)
                self.end_spin.setValue(sample_value)
                self.end_spin.blockSignals(False)
                self.waveform.set_loop_points(start, sample_value)
                self.update_duration_label(start, sample_value)
    
    def update_time_spinboxes(self):
        """Update time spinboxes for loop points"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            self.start_time_spin.blockSignals(True)
            self.end_time_spin.blockSignals(True)
            
            start_time = self.start_spin.value() / sample_rate
            end_time = self.end_spin.value() / sample_rate
            
            self.start_time_spin.setValue(start_time)
            self.end_time_spin.setValue(end_time)
            
            self.start_time_spin.blockSignals(False)
            self.end_time_spin.blockSignals(False)
    
    def update_time_labels(self):
        """Update time spinboxes for loop points (backward compatibility)"""
        self.update_time_spinboxes()
    
    def update_loop_info(self, start: int, end: int):
        """Update loop information displays"""
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        self.start_time_spin.blockSignals(True)
        self.end_time_spin.blockSignals(True)
        
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)
        
        # Update time spinboxes
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        if sample_rate > 0:
            self.start_time_spin.setValue(start / sample_rate)
            self.end_time_spin.setValue(end / sample_rate)
        
        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        self.start_time_spin.blockSignals(False)
        self.end_time_spin.blockSignals(False)
        
        self.update_duration_label(start, end)
    
    def update_duration_label(self, start: int, end: int):
        """Update duration label"""
        if end > start:
            duration_samples = end - start
            file_info = self.loop_manager.get_file_info()
            duration_seconds = duration_samples / file_info['sample_rate']
            self.duration_label.setText(f"{duration_samples} samples ({duration_seconds:.2f}s)")
        else:
            self.duration_label.setText("0 samples")
    
    def clear_loop_points(self):
        """Clear loop points - set to track start and end"""
        file_info = self.loop_manager.get_file_info()
        track_end = file_info.get('total_samples', 0)
        self.waveform.set_loop_points(0, track_end)
        self.update_loop_info(0, track_end)

    def on_mode_changed(self, mode: str):
        """Switch between loop editing and trim handles"""
        self.waveform.set_mode(mode)
        # Keep UI buttons in sync
        if mode == 'loop':
            self.mode_loop_radio.setChecked(True)
        else:
            self.mode_trim_radio.setChecked(True)
        self.update_trim_label()

    def update_trim_label(self):
        """Update trim label text with current range"""
        if not self.waveform or self.waveform.total_samples == 0:
            self.trim_label.setText("Trim: n/a")
            return
        sr = self.waveform.sample_rate or 1
        start_sec = self.waveform.trim_start / sr
        end_sec = self.waveform.trim_end / sr
        total_sec = self.waveform.total_samples / sr
        self.trim_label.setText(
            f"Trim: {start_sec:.3f}s → {end_sec:.3f}s of {total_sec:.3f}s"
        )

    def on_reset_trim(self):
        """Reset trim to full length"""
        self.waveform.reset_trim_points()
        self.update_trim_label()

    def on_apply_trim(self):
        """Apply trim to working audio using current trim handles"""
        if not self.waveform or self.waveform.total_samples == 0:
            QMessageBox.warning(self, "No Audio", "Load audio before trimming.")
            return

        trim_start = self.waveform.trim_start
        trim_end = self.waveform.trim_end

        if trim_end - trim_start < 10:
            QMessageBox.warning(self, "Trim Too Small", "Trim range is too small.")
            return

        if trim_end <= trim_start:
            QMessageBox.warning(self, "Invalid Trim", "Trim end must be after trim start.")
            return

        ok = self.loop_manager.trim_audio(trim_start, trim_end)
        if not ok:
            QMessageBox.critical(self, "Trim Failed", "Unable to trim audio. Check the log for details.")
            return

        # Reload audio data and refresh UI
        self.load_audio_data()
        self.waveform.set_mode('loop')
        self.mode_loop_radio.setChecked(True)
        self.update_trim_label()
    
    def _save_volume_adjusted_audio(self) -> bool:
        """Save volume-adjusted audio data back to the temp WAV file"""
        if not self._volume_adjusted or self.waveform.audio_data is None:
            return True  # No volume adjustment to save
        
        try:
            import wave
            import struct
            import time
            import tempfile
            import shutil
            import os
            
            wav_path = self.loop_manager.get_wav_path()
            if not wav_path:
                logging.error("No WAV path available for saving volume adjustments")
                return False
            
            # Stop media player to release file handle
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState
            self.media_player.stop()
            
            # Clear media to fully release file handle
            self.media_player.setMedia(QMediaContent())
            
            # Give more time for the file to be released (Windows can be slow)
            import time
            time.sleep(0.3)  # Increased from 0.1 to 0.3 seconds
            
            # Check if file is accessible before attempting to write
            try:
                # Try to open the file in append mode to test accessibility
                with open(wav_path, 'ab') as test_file:
                    pass  # Just test if we can open it
            except PermissionError:
                logging.warning("File still locked, waiting longer...")
                time.sleep(0.5)  # Wait even longer
                try:
                    with open(wav_path, 'ab') as test_file:
                        pass
                except PermissionError:
                    QMessageBox.critical(None, "File Access Error",
                                       f"Cannot access audio file for volume changes.\n\n"
                                       f"The file may be locked by another process.\n"
                                       f"Try closing and reopening the Loop Editor.")
                    return False
            
            # Read original WAV file info first
            try:
                with wave.open(wav_path, 'rb') as original_wav:
                    channels = original_wav.getnchannels()
                    sample_width = original_wav.getsampwidth()
                    sample_rate = original_wav.getframerate()
            except Exception as e:
                logging.error(f"Error reading original WAV file info: {e}")
                return False
            
            # Convert adjusted audio data back to the original format
            adjusted_data = self.waveform.audio_data
            
            # Scale back to original bit depth
            if sample_width == 1:  # 8-bit
                # Convert from float32 [-1,1] to uint8 [0,255]
                audio_int = ((adjusted_data + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            elif sample_width == 2:  # 16-bit
                # Convert from float32 [-1,1] to int16 [-32768,32767]
                audio_int = (adjusted_data * 32767).clip(-32768, 32767).astype(np.int16)
            elif sample_width == 3:  # 24-bit
                # Convert from float32 [-1,1] to int32, then extract 24 bits
                audio_int32 = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
                # Convert to bytes and extract middle 3 bytes (24-bit)
                audio_bytes = audio_int32.view(np.uint8).reshape(-1, 4)
                audio_int = audio_bytes[:, 1:4].flatten()  # Take bytes 1-3 (24-bit portion)
            elif sample_width == 4:  # 32-bit
                # Convert from float32 [-1,1] to int32
                audio_int = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
            else:
                logging.error(f"Unsupported sample width: {sample_width}")
                return False
            
            # Handle stereo conversion if original was stereo
            if channels == 2:
                if sample_width == 3:
                    # For 24-bit, we already have bytes, need to handle differently
                    # audio_int is already flattened bytes, reshape for stereo duplication
                    mono_samples = len(audio_int) // 3
                    audio_24bit = audio_int.reshape(mono_samples, 3)
                    stereo_data = np.empty((mono_samples * 2, 3), dtype=np.uint8)
                    stereo_data[0::2] = audio_24bit  # Left channel
                    stereo_data[1::2] = audio_24bit  # Right channel (duplicate)
                    audio_int = stereo_data.flatten()
                else:
                    # Duplicate mono to stereo (interleave)
                    stereo_data = np.empty(len(audio_int) * 2, dtype=audio_int.dtype)
                    stereo_data[0::2] = audio_int  # Left channel
                    stereo_data[1::2] = audio_int  # Right channel (duplicate)
                    audio_int = stereo_data
            
            # Write new WAV file with proper error handling and retry
            # Use temporary file approach to avoid file locking issues
            import tempfile
            import shutil
            
            temp_wav_path = None
            try:
                # Create temporary file in the same directory
                temp_dir = os.path.dirname(wav_path)
                temp_fd, temp_wav_path = tempfile.mkstemp(suffix='.wav', dir=temp_dir)
                os.close(temp_fd)  # Close the file descriptor
                
                # Write to temporary file first
                with wave.open(temp_wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(sample_width)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int.tobytes())
                
                # Now try to replace the original file
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        shutil.move(temp_wav_path, wav_path)
                        break  # Success
                    except PermissionError as e:
                        if attempt < max_retries - 1:
                            logging.warning(f"Permission denied replacing file on attempt {attempt + 1}, retrying...")
                            time.sleep(0.3)
                            continue
                        else:
                            logging.error(f"Permission denied replacing WAV file after {max_retries} attempts: {e}")
                            QMessageBox.critical(None, "File Access Error", 
                                               f"Cannot save volume changes: File is in use or write-protected.\n\n"
                                               f"Please ensure the file is not open in another application.\n"
                                               f"You may need to restart the application if the file remains locked.")
                            return False
                            
            except Exception as e:
                logging.error(f"Error writing WAV file: {e}")
                return False
            finally:
                # Clean up temporary file if it still exists
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                    except:
                        pass  # Ignore cleanup errors
            
            logging.info(f"Saved volume-adjusted audio to {wav_path}")
            
            # Reload media if it was playing
            if was_playing and wav_path:
                url = QUrl.fromLocalFile(wav_path)
                self.media_player.setMedia(QMediaContent(url))
                
            return True
            
        except Exception as e:
            logging.error(f"Error saving volume-adjusted audio: {e}")
            return False
    
    def _reload_media_after_volume_change(self):
        """Force reload media player after volume changes are saved"""
        try:
            wav_path = self.loop_manager.get_wav_path()
            if not wav_path:
                return
            
            # Clear current media to force reload
            self.media_player.setMedia(QMediaContent())
            
            # Wait a moment for the clear to take effect
            QTimer.singleShot(50, lambda: self._set_fresh_media(wav_path))
            
        except Exception as e:
            logging.error(f"Error reloading media after volume change: {e}")
    
    def _set_fresh_media(self, wav_path: str):
        """Set fresh media content after a brief delay"""
        try:
            url = QUrl.fromLocalFile(wav_path)
            self.media_player.setMedia(QMediaContent(url))
            logging.info("Media player reloaded with volume-adjusted audio")
        except Exception as e:
            logging.error(f"Error setting fresh media: {e}")
    
    def _force_media_refresh(self):
        """Force media player to reload for immediate volume change preview"""
        try:
            # Clear the media player cache by setting empty content then reloading
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())
            
            # Small delay then reload
            QTimer.singleShot(100, self._reload_current_media)
            
        except Exception as e:
            logging.error(f"Error forcing media refresh: {e}")
    
    def _reload_current_media(self):
        """Reload the current media file"""
        try:
            # Use temporary file if volume was adjusted, otherwise use original
            wav_path = self._get_playback_wav_path()
            if wav_path:
                url = QUrl.fromLocalFile(wav_path)
                self.media_player.setMedia(QMediaContent(url))
                logging.info(f"Forced media refresh after volume adjustment: {wav_path}")
        except Exception as e:
            logging.error(f"Error reloading current media: {e}")
    
    def _write_volume_to_wav_immediately(self) -> bool:
        """Write volume-adjusted audio to temporary file for immediate playback"""
        try:
            # Use the new temporary file approach instead of writing to original
            return self._write_volume_to_temp_file()
        except Exception as e:
            logging.error(f"Error writing volume to temp file immediately: {e}")
            return False
    
    def _create_temp_wav_file(self) -> str:
        """Create a temporary WAV file for volume adjustments"""
        try:
            import tempfile
            import shutil
            
            # Get original WAV path
            original_path = self.loop_manager.get_wav_path()
            if not original_path:
                raise ValueError("No original WAV path available")
            
            # Store original path if not already stored
            if not self._original_wav_path:
                self._original_wav_path = original_path
            
            # Create temporary file in system temp directory instead of project root
            temp_fd, temp_path = tempfile.mkstemp(suffix='_volume_temp.wav', prefix='scdtoolkit_')
            os.close(temp_fd)  # Close the file descriptor
            
            # Copy original file to temporary location
            shutil.copy2(original_path, temp_path)
            
            self._temp_wav_path = temp_path
            self._temp_file_created = True
            
            logging.info(f"Created temporary WAV file: {temp_path}")
            return temp_path
            
        except Exception as e:
            logging.error(f"Error creating temporary WAV file: {e}")
            return None
    
    def _write_volume_to_temp_file(self) -> bool:
        """Write volume-adjusted audio to temporary file for playback"""
        if not self._volume_adjusted or self.waveform.audio_data is None:
            return True  # Nothing to write
        
        try:
            # Create temp file if it doesn't exist
            if not self._temp_wav_path or not os.path.exists(self._temp_wav_path):
                temp_path = self._create_temp_wav_file()
                if not temp_path:
                    return False
                self._temp_wav_path = temp_path
            
            # Stop media player to release any handles on temp file
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())
            
            # Small delay to ensure file handle release
            import time
            time.sleep(0.1)
            
            # Read original WAV file info
            original_path = self._original_wav_path or self.loop_manager.get_wav_path()
            with wave.open(original_path, 'rb') as original_wav:
                channels = original_wav.getnchannels()
                sample_width = original_wav.getsampwidth()
                sample_rate = original_wav.getframerate()
            
            # Convert adjusted audio data back to the original format
            adjusted_data = self.waveform.audio_data
            
            # Scale back to original bit depth
            if sample_width == 1:  # 8-bit
                audio_int = ((adjusted_data + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            elif sample_width == 2:  # 16-bit
                audio_int = (adjusted_data * 32767).clip(-32768, 32767).astype(np.int16)
            elif sample_width == 3:  # 24-bit
                # Convert from float32 [-1,1] to int32, then extract 24 bits
                audio_int32 = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
                # Convert to bytes and extract middle 3 bytes (24-bit)
                audio_bytes = audio_int32.view(np.uint8).reshape(-1, 4)
                audio_int = audio_bytes[:, 1:4].flatten()  # Take bytes 1-3 (24-bit portion)
            elif sample_width == 4:  # 32-bit
                audio_int = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
            else:
                logging.error(f"Unsupported sample width: {sample_width}")
                return False
            
            # Handle stereo conversion if original was stereo
            if channels == 2:
                if sample_width == 3:
                    # For 24-bit, we already have bytes, need to handle differently
                    mono_samples = len(audio_int) // 3
                    audio_24bit = audio_int.reshape(mono_samples, 3)
                    stereo_data = np.empty((mono_samples * 2, 3), dtype=np.uint8)
                    stereo_data[0::2] = audio_24bit  # Left channel
                    stereo_data[1::2] = audio_24bit  # Right channel (duplicate)
                    audio_int = stereo_data.flatten()
                else:
                    stereo_data = np.empty(len(audio_int) * 2, dtype=audio_int.dtype)
                    stereo_data[0::2] = audio_int  # Left channel
                    stereo_data[1::2] = audio_int  # Right channel (duplicate)
                    audio_int = stereo_data
            
            # Write to temporary file
            with wave.open(self._temp_wav_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int.tobytes())
            
            logging.info(f"Volume-adjusted audio written to temp file: {self._temp_wav_path}")
            
            # Reload media player with temp file if it was playing
            if was_playing:
                url = QUrl.fromLocalFile(self._temp_wav_path)
                self.media_player.setMedia(QMediaContent(url))
            
            return True
            
        except Exception as e:
            logging.error(f"Error writing volume to temp file: {e}")
            return False
    
    def _get_playback_wav_path(self) -> str:
        """Get the WAV path to use for playback (temp file if volume adjusted, original otherwise)"""
        if self._volume_adjusted and self._temp_wav_path and os.path.exists(self._temp_wav_path):
            return self._temp_wav_path
        return self.loop_manager.get_wav_path()

    def _start_loudness_worker(self, mode: str, wav_path: str, *, target_i: float = -12.0, target_tp: float = -1.0, delta_i: float = None):
        """Start loudness analysis/normalization in the background"""
        try:
            if hasattr(self, '_loudness_worker') and self._loudness_worker and self._loudness_worker.isRunning():
                return False  # already running

            worker = LoudnessWorker(mode, wav_path, target_i=target_i, target_tp=target_tp, delta_i=delta_i)
            worker.analyze_finished.connect(self._on_true_loudness_ready)
            worker.normalize_finished.connect(self._on_loudnorm_finished)
            worker.error.connect(self._on_loudness_error)
            self._loudness_worker = worker
            worker.start()
            return True
        except Exception as e:
            logging.error(f"Failed to start loudness worker: {e}")
            return False

    def _on_true_loudness_ready(self, loudness):
        """Handle completion of background true loudness analysis"""
        try:
            analysis_text = "=== AUDIO LEVEL ANALYSIS ===\n\n"
            if loudness:
                analysis_text += f"Integrated (LUFS): {loudness['input_i']:.1f} LUFS\n"
                analysis_text += f"True Peak       : {loudness['input_tp']:.1f} dBTP\n"
                analysis_text += f"Loudness Range  : {loudness['input_lra']:.1f} dB\n"
                analysis_text += f"Threshold       : {loudness['input_thresh']:.1f} dB\n"
                analysis_text += f"Target Offset   : {loudness['target_offset']:.2f} dB\n"

                # Recommendations
                analysis_text += "\n=== RECOMMENDATIONS ===\n"
                tp = loudness['input_tp']
                i_val = loudness['input_i']
                if tp > -0.1:
                    analysis_text += f"\n⚠️ True peak {tp:.1f} dBTP may clip. Reduce ~{tp + 1.0:.1f} dB to hit -1 dBTP.\n"
                elif tp > -1.0:
                    analysis_text += f"\nℹ️ True peak {tp:.1f} dBTP is near headroom.\n"
                if -13.0 <= i_val <= -11.0:
                    analysis_text += f"\nℹ️ Integrated loudness {i_val:.1f} LUFS matches target range (around -12).\n"
                elif i_val > -11.0:
                    analysis_text += f"\n⚠️ Integrated loudness {i_val:.1f} LUFS is hot; consider lowering toward -12 LUFS.\n"
                else:
                    analysis_text += f"\nℹ️ Integrated loudness {i_val:.1f} LUFS is below target; normalize to -12 LUFS.\n"
            else:
                analysis_text += "True loudness unavailable (ffmpeg not found).\n"

            # Append file info
            file_info = self.loop_manager.get_file_info()
            duration_seconds = file_info.get('total_samples', 0) / file_info.get('sample_rate', 44100)
            analysis_text += f"\n=== FILE INFO ===\n"
            analysis_text += f"Sample Rate    : {file_info.get('sample_rate', 0)} Hz\n"
            analysis_text += f"Duration       : {self.format_time(duration_seconds)}\n"
            analysis_text += f"Total Samples  : {file_info.get('total_samples', 0):,}\n"

            self.analysis_text.setText(analysis_text)
            self._hide_busy()
        except Exception as e:
            logging.error(f"Error updating loudness analysis: {e}")

    def _on_loudnorm_finished(self, success: bool, loudness):
        """Handle completion of background loudness normalization"""
        try:
            # Re-enable button
            self.adjust_volume_btn.setEnabled(True)
            self.increase_lufs_btn.setEnabled(True)
            self.decrease_lufs_btn.setEnabled(True)
            self._hide_busy()

            if not success:
                QMessageBox.critical(self, "Normalization Failed", "Could not apply loudness normalization. Check logs for details.")
                return

            # Restore loop metadata
            start, end = getattr(self, '_pending_loop_restore', (0, 0))
            if end > start:
                self.loop_manager.set_loop_points(start, end)

            # Refresh loop manager info
            wav_path = self.loop_manager.get_wav_path()
            try:
                self.loop_manager._analyze_wav_file(wav_path)
            except Exception:
                pass

            # Reload audio and refresh UI
            self.load_audio_data()
            self._volume_adjusted = True
            self.reset_volume_btn.setEnabled(True)
            self._force_media_refresh()
            QTimer.singleShot(100, self.analyze_audio)
            
        except Exception as e:
            logging.error(f"Error finalizing loudnorm: {e}")

    def _on_loudness_error(self, msg: str):
        """Handle worker errors"""
        logging.error(f"Loudness worker error: {msg}")
        self.adjust_volume_btn.setEnabled(True)
        self.increase_lufs_btn.setEnabled(True)
        self.decrease_lufs_btn.setEnabled(True)
        self._hide_busy()
        QMessageBox.critical(self, "Loudness Error", msg)
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            if self._temp_wav_path and os.path.exists(self._temp_wav_path):
                # Stop media player first
                self.media_player.stop()
                self.media_player.setMedia(QMediaContent())
                
                # Small delay to ensure file handle release
                import time
                time.sleep(0.1)
                
                # Remove temp file
                os.remove(self._temp_wav_path)
                logging.info(f"Cleaned up temporary file: {self._temp_wav_path}")
                
            self._temp_wav_path = None
            self._temp_file_created = False
            
        except Exception as e:
            logging.error(f"Error cleaning up temp files: {e}")
    
    def save_changes(self):
        """Save loop points and volume changes, then close"""
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        logging.debug(f"Save changes - start: {start}, end: {end}")
        
        if end <= start and end > 0:
            QMessageBox.warning(self, "Invalid Loop", "Loop end must be greater than loop start")
            return
        
        # First, save volume-adjusted audio data if it was modified
        if self._volume_adjusted and self._temp_wav_path and os.path.exists(self._temp_wav_path):
            # Copy temporary file back to original location
            try:
                import shutil
                original_path = self._original_wav_path or self.loop_manager.get_wav_path()
                
                # Stop media player to release file handles
                self.media_player.stop()
                self.media_player.setMedia(QMediaContent())
                
                # Small delay to ensure file handle release
                import time
                time.sleep(0.2)
                
                # Copy temp file to original location
                shutil.copy2(self._temp_wav_path, original_path)
                logging.info(f"Volume-adjusted audio saved to original file: {original_path}")
                
            except Exception as e:
                logging.error(f"Error saving volume changes to original file: {e}")
                QMessageBox.warning(self, "Save Warning", 
                                  f"Could not save volume changes to original file.\n"
                                  f"Loop points will be saved, but volume changes may not persist.\n\n"
                                  f"Error: {str(e)}")
        
        # Save loop points to loop manager
        if end > start and end > 0:
            logging.debug(f"Saving loop points: {start} -> {end}")
            success = self.loop_manager.set_loop_points(start, end)
            if success:
                # Check if this is an SCD file that will need conversion
                if hasattr(self.loop_manager, 'original_scd_path') and self.loop_manager.original_scd_path:
                    # Show progress dialog for SCD conversion
                    self._save_with_progress()
                    return
                else:
                    # Save the actual loop data to file (WAV - quick operation)
                    success = self.loop_manager.save_loop_points()
        else:
            logging.debug(f"Clearing loop points (start={start}, end={end})")
            success = self.loop_manager.clear_loop_points()
        
        if success:
            # Stop playback and all timers before closing
            self.media_player.stop()
            self.position_timer.stop()
            self.loop_timer.stop()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save loop points")
    
    def _save_with_progress(self):
        """Save SCD file with progress dialog"""
        # Create progress dialog
        progress = QProgressDialog("Saving SCD", "Cancel", 0, 0, self)
        progress.setWindowTitle("Saving Audio File")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)  # Show immediately
        progress.setCancelButton(None)  # No cancel button - operation must complete
        progress.setRange(0, 0)  # Indeterminate progress
        progress.show()
        
        # Process events to show the dialog
        QApplication.processEvents()
        
        try:
            # Create a worker thread for the save operation
            worker = SaveWorker(self.loop_manager)
            worker.finished.connect(self._on_save_finished)
            worker.error.connect(self._on_save_error)
            
            # Keep reference to prevent garbage collection
            self._save_worker = worker
            self._progress_dialog = progress
            
            # Start the worker
            worker.start()
            
        except Exception as e:
            progress.close()
            logging.error(f"Error starting save operation: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to start save operation: {str(e)}")
    
    def _on_save_finished(self, success):
        """Handle save operation completion"""
        try:
            if hasattr(self, '_progress_dialog'):
                self._progress_dialog.close()
            
            if success:
                logging.info("SCD save operation completed successfully")
                try:
                    # Mark sanitized cache for the saved SCD so exports skip re-processing
                    if getattr(self.loop_manager, "original_scd_path", None) and getattr(self.parent_window, "converter", None):
                        self.parent_window.converter.mark_sanitized(self.loop_manager.original_scd_path)
                except Exception:
                    logging.debug("Could not mark sanitized cache after loop save")
                # Stop playback and all timers before closing
                self.media_player.stop()
                self.position_timer.stop()
                self.loop_timer.stop()
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to save loop points to SCD file")
                
        except Exception as e:
            logging.error(f"Error handling save completion: {e}")
        finally:
            # Clean up worker reference
            if hasattr(self, '_save_worker'):
                delattr(self, '_save_worker')
            if hasattr(self, '_progress_dialog'):
                delattr(self, '_progress_dialog')
    
    def _on_save_error(self, error_msg):
        """Handle save operation error"""
        try:
            if hasattr(self, '_progress_dialog'):
                self._progress_dialog.close()
            
            logging.error(f"Save operation failed: {error_msg}")
            QMessageBox.critical(self, "Save Error", f"Failed to save SCD file:\n{error_msg}")
            
        except Exception as e:
            logging.error(f"Error handling save error: {e}")
        finally:
            # Clean up worker reference
            if hasattr(self, '_save_worker'):
                delattr(self, '_save_worker')
            if hasattr(self, '_progress_dialog'):
                delattr(self, '_progress_dialog')
    
    def cancel_dialog(self):
        """Cancel dialog and stop playback"""
        self.media_player.stop()
        self.position_timer.stop()
        self.loop_timer.stop()
        self.reject()
    
    # Playback methods
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            # Stop position updates when paused
            self.position_timer.stop()
        elif self.media_player.state() == QMediaPlayer.PausedState:
            # Resume from current position
            self.media_player.play()
            # Restart position updates
            self.position_timer.start(8)  # ~120 FPS for ultra-smooth updates
            if self.is_loop_testing:
                self.loop_timer.start(16)
        else:
            # Start fresh playback
            self.start_playback()
    
    def start_playback(self):
        """Start playback"""
        # Use temporary file if volume was adjusted, otherwise use original
        wav_path = self._get_playback_wav_path()
        if not wav_path or not os.path.exists(wav_path):
            QMessageBox.warning(self, "Error", "No audio file available for playback")
            return

        # Get current cursor position from waveform first
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        target_position_ms = 0
        
        if hasattr(self.waveform, 'current_position'):
            current_sample_pos = self.waveform.current_position
            target_position_ms = int((current_sample_pos / sample_rate) * 1000)

        # Only set media content if it's different or not set
        current_media = self.media_player.media()
        new_url = QUrl.fromLocalFile(wav_path)
        media_changed = (current_media.isNull() or 
                        current_media.canonicalUrl() != new_url)
        
        if media_changed:
            self.media_player.setMedia(QMediaContent(new_url))
            logging.info(f"Loaded media for playbook: {wav_path}")
            # Store target position for after playback starts
            self._target_position_ms = target_position_ms
        else:
            # Media already loaded, set position immediately
            self.media_player.setPosition(target_position_ms)
            self._target_position_ms = None
        
        # If loop mode is on and we're outside the loop, start from loop beginning
        if self.is_loop_testing:
            start = self.start_spin.value()
            end = self.end_spin.value()
            
            if start < end:  # Valid loop points
                start_ms = int((start / sample_rate) * 1000)
                end_ms = int((end / sample_rate) * 1000)
                
                # If current position is outside loop, start from loop beginning
                if target_position_ms < start_ms or target_position_ms >= end_ms:
                    if media_changed:
                        self._target_position_ms = start_ms
                    else:
                        self.media_player.setPosition(start_ms)

        self.media_player.play()
        
        # If we have a target position to set after media starts, do it with a short delay
        if hasattr(self, '_target_position_ms') and self._target_position_ms is not None:
            QTimer.singleShot(100, lambda: self._set_delayed_position(self._target_position_ms))
        
        # Start ultra-smooth position updates
        self.position_timer.start(8)  # ~120 FPS for ultra-smooth updates
        
        # Start loop timer if loop mode is enabled
        if self.is_loop_testing:
            self.loop_timer.start(16)  # ~60 FPS for smooth visual updates
            
    def _set_delayed_position(self, position_ms):
        """Set media position after a short delay to ensure media is ready"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.setPosition(position_ms)
            self._target_position_ms = None
            
    def stop_playback(self):
        """Stop all playback"""
        self.media_player.stop()
        
        # Stop all timers
        self.position_timer.stop()
        self.loop_timer.stop()
    
    def toggle_loop_mode(self):
        """Toggle loop mode on/off"""
        self.is_loop_testing = self.loop_test_btn.isChecked()
        
        if self.is_loop_testing:
            # Start loop timer if playing
            if self.media_player.state() == QMediaPlayer.PlayingState:
                self.loop_timer.start(16)  # ~60 FPS for smooth visual updates
        else:
            # Stop loop timer
            self.loop_timer.stop()
    
    def toggle_follow_mode(self):
        """Toggle the auto-follow mode for the playback cursor"""
        if self.waveform.audio_data is None:
            return
        
        # Simple, robust toggle - works immediately regardless of playback state
        if self.waveform.is_focused_on_position:
            # Currently following, turn it off
            self.waveform.is_focused_on_position = False
        else:
            # Not following, turn it on and immediately center if cursor is visible
            self.waveform.is_focused_on_position = True
            # Center on current position to start following
            self._center_on_current_position()
        
        # Force visual update to show new state
        self.waveform.update()
    
    def focus_on_current_position(self):
        """Center the view on current position (legacy method - kept for compatibility)"""
        self._center_on_current_position()
    
    def _zoom_to_full_track(self):
        """Zoom out to show the entire track"""
        if self.waveform.audio_data is None:
            return
        
        # Set zoom to show the full track
        self.waveform.samples_per_pixel = max(1, self.waveform.total_samples / self.waveform.width())
        self.waveform.scroll_position = 0
        self.waveform.is_focused_on_position = False
        self.waveform.update()
    
    def on_volume_changed(self, value: int):
        """Handle volume control changes."""
        if hasattr(self, 'media_player'):
            self.media_player.setVolume(int(value))
        
        # Update display
        self.waveform.update()
        self.update_scrollbar_range()
        self.waveform_scroll.setValue(0)
    
    def _center_on_current_position(self):
        """Center the waveform view on the current playback position"""
        if not hasattr(self.waveform, 'current_position'):
            return
        
        current_sample = self.waveform.current_position
        
        # Calculate the scroll position to center the current position
        # We want the current position to be in the middle of the visible area
        visible_samples = self.waveform.width() * self.waveform.samples_per_pixel
        center_scroll_pos = (current_sample / self.waveform.samples_per_pixel) - (self.waveform.width() / 2)
        
        # Ensure scroll position is within valid bounds
        max_scroll = max(0, (self.waveform.total_samples / self.waveform.samples_per_pixel) - self.waveform.width())
        center_scroll_pos = max(0, min(center_scroll_pos, max_scroll))
        
        # Set flags to prevent focus state reset during this scroll
        self.waveform._setting_focus_scroll = True
        self.waveform._programmatic_scroll = True
        
        # Update the waveform scroll position
        self.waveform.set_scroll_position(center_scroll_pos)
        self.waveform.is_focused_on_position = True
        
        # Clear the flags
        if hasattr(self.waveform, '_setting_focus_scroll'):
            delattr(self.waveform, '_setting_focus_scroll')
        if hasattr(self.waveform, '_programmatic_scroll'):
            delattr(self.waveform, '_programmatic_scroll')
        
        # Update the scrollbar to match
        self.waveform_scroll.setValue(int(center_scroll_pos))
    
    def follow_playback_cursor(self, current_sample):
        """Auto-follow the playback cursor when in focused mode"""
        if not self.waveform.is_focused_on_position:
            return
        
        # Calculate current cursor position in pixels
        cursor_pixel = (current_sample / self.waveform.samples_per_pixel) - self.waveform.scroll_position
        
        # Check if cursor is getting close to the edges of the visible area
        width = self.waveform.width()
        margin = width * 0.25  # 25% margin on each side
        
        # If cursor is outside the comfortable viewing area, re-center
        if cursor_pixel < margin or cursor_pixel > (width - margin):
            # Throttle rapid re-centering but don't block the toggle functionality
            import time
            current_time = time.time() * 1000
            if current_time - self.waveform._last_follow_time < self.waveform._follow_cooldown:
                return  # Skip this scroll update but keep following enabled
            
            # Calculate new scroll position to center the cursor
            center_scroll_pos = (current_sample / self.waveform.samples_per_pixel) - (width / 2)
            
            # Ensure scroll position is within valid bounds
            max_scroll = max(0, (self.waveform.total_samples / self.waveform.samples_per_pixel) - width)
            center_scroll_pos = max(0, min(center_scroll_pos, max_scroll))
            
            # Set flags to prevent focus state reset during this scroll
            self.waveform._setting_focus_scroll = True
            self.waveform._programmatic_scroll = True
            
            # Use smooth scrolling to the new position
            self.waveform.smooth_scroll_to(center_scroll_pos)
            
            # Clear the flags
            if hasattr(self.waveform, '_setting_focus_scroll'):
                delattr(self.waveform, '_setting_focus_scroll')
            if hasattr(self.waveform, '_programmatic_scroll'):
                delattr(self.waveform, '_programmatic_scroll')
            
            # Update the last follow time
            self.waveform._last_follow_time = current_time
    
    def update_sample_position(self):
        """Update position display with sample-accurate timing"""
        if self.media_player.state() != QMediaPlayer.PlayingState:
            return
            
        current_ms = self.media_player.position()
        if self.media_player.duration() > 0:
            # Ultra-smooth time display
            current_time = self.format_time(current_ms / 1000.0)
            total_time = self.format_time(self.media_player.duration() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
        
        # Update waveform position with exact sample accuracy
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        sample_position = int((current_ms / 1000.0) * sample_rate)
        
        if hasattr(self.waveform, 'set_current_position'):
            self.waveform.set_current_position(sample_position)

    def check_loop_position(self):
        """Check if we need to loop back to start"""
        if not self.is_loop_testing or self.media_player.state() != QMediaPlayer.PlayingState:
            return
        
        current_ms = self.media_player.position()
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        if start >= end:
            return
        
        start_ms = int((start / sample_rate) * 1000)
        end_ms = int((end / sample_rate) * 1000)
        
        # If we've reached the loop end, jump back to start
        if current_ms >= end_ms - 50:  # 50ms buffer
            self.media_player.setPosition(start_ms)
    
    def on_playback_position_changed(self, position):
        """Handle playback position changes"""
        if self.media_player.duration() > 0:
            current_time = self.format_time(position / 1000.0)
            total_time = self.format_time(self.media_player.duration() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
        
        # Update waveform position
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        sample_position = int((position / 1000.0) * sample_rate)
        
        if hasattr(self.waveform, 'set_current_position'):
            self.waveform.set_current_position(sample_position)
    
    def on_playback_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")
    
    def on_duration_changed(self, duration):
        """Handle duration changes"""
        if duration > 0:
            total_time = self.format_time(duration / 1000.0)
            current_time = self.format_time(self.media_player.position() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
    
    def format_time(self, seconds):
        """Format time in mm:ss format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
    
    def analyze_audio(self):
        """Analyze the current audio file for level information"""
        if self.waveform.audio_data is None or len(self.waveform.audio_data) == 0:
            self.analysis_text.setText("No audio data available for analysis")
            return
        
        try:
            analyzer = AudioAnalyzer()

            # Quick approximate while we spin up true loudness worker
            levels = analyzer.analyze_audio_levels(
                self.waveform.audio_data,
                self.waveform.sample_rate
            )

            # File info
            file_info = self.loop_manager.get_file_info()
            duration_seconds = file_info.get('total_samples', 0) / file_info.get('sample_rate', 44100)

            analysis_text = "=== AUDIO LEVEL ANALYSIS ===\n\n"
            analysis_text += "Calculating true loudness (ffmpeg loudnorm)...\n"
            analysis_text += f"Approx Peak    : {levels.peak_db:.1f} dB\n"
            analysis_text += f"Approx RMS     : {levels.rms_db:.1f} dB\n"

            analysis_text += "\n=== FILE INFO ===\n"
            analysis_text += f"Sample Rate    : {file_info.get('sample_rate', 0)} Hz\n"
            analysis_text += f"Duration       : {self.format_time(duration_seconds)}\n"
            analysis_text += f"Total Samples  : {file_info.get('total_samples', 0):,}\n"

            self.analysis_text.setText(analysis_text)

            # Start background true loudness worker
            wav_path = self.loop_manager.get_wav_path()
            if wav_path:
                if self._start_loudness_worker(mode="analyze", wav_path=wav_path):
                    self._show_busy("Analyzing audio (true loudness)...")

            # Enable consolidated volume button after kick-off
            self.adjust_volume_btn.setEnabled(True)
            self.increase_lufs_btn.setEnabled(True)
            self.decrease_lufs_btn.setEnabled(True)
            self.reset_volume_btn.setEnabled(self._volume_adjusted)

        except Exception as e:
            logging.error(f"Error during audio analysis: {e}")
            self.analysis_text.setText(f"Error analyzing audio: {str(e)}")
    
    def auto_volume_adjustment(self):
        """Apply automatic volume adjustment targeting realistic game audio levels"""
        self._apply_volume_adjustment("auto")
    
    def normalize_peak(self):
        """Normalize audio to -0.2dB peak level (typical game audio)"""
        self._apply_volume_adjustment("peak")
    
    def normalize_rms(self):
        """Normalize audio to -15dB RMS level (game audio range)"""
        self._apply_volume_adjustment("rms")

    def adjust_volume_lufs(self):
        """Normalize audio to -12 LUFS / -1 dBTP using ffmpeg loudnorm (matches official SCD files)"""
        wav_path = self.loop_manager.get_wav_path()
        if not wav_path:
            QMessageBox.warning(self, "No Audio", "No audio file available for loudness normalization")
            return
        self._prepare_loudness_edit()
        # Preserve current loop points so we can re-apply metadata after normalization
        self._pending_loop_restore = self.loop_manager.get_loop_points()

        # Disable button to prevent re-entry and show progress text
        self.adjust_volume_btn.setEnabled(False)
        self.increase_lufs_btn.setEnabled(False)
        self.decrease_lufs_btn.setEnabled(False)
        self.analysis_text.setText("Normalizing to -12 LUFS / -1 dBTP (background)...")
        self._show_busy("Normalizing to -12 LUFS / -1 dBTP...")

        if not self._start_loudness_worker(mode="normalize", wav_path=wav_path, target_i=-12.0, target_tp=-1.0):
            self._hide_busy()
            self.adjust_volume_btn.setEnabled(True)
            self.increase_lufs_btn.setEnabled(True)
            self.decrease_lufs_btn.setEnabled(True)
            QMessageBox.warning(self, "Busy", "Another loudness task is already running.")

    def adjust_volume_relative(self, delta_lufs: float):
        """Raise or lower loudness by a relative LUFS offset using loudnorm"""
        wav_path = self.loop_manager.get_wav_path()
        if not wav_path:
            QMessageBox.warning(self, "No Audio", "No audio file available for loudness adjustment")
            return
        self._prepare_loudness_edit()

        # Preserve current loop points so we can re-apply metadata after normalization
        self._pending_loop_restore = self.loop_manager.get_loop_points()

        # Disable buttons to prevent re-entry and show progress text
        self.adjust_volume_btn.setEnabled(False)
        self.increase_lufs_btn.setEnabled(False)
        self.decrease_lufs_btn.setEnabled(False)

        direction = "Increasing" if delta_lufs > 0 else "Decreasing"
        self.analysis_text.setText(f"{direction} loudness by {delta_lufs:+.1f} LUFS (background)...")
        self._show_busy(f"{direction} loudness by {delta_lufs:+.1f} LUFS...")

        # Use relative mode which measures current loudness then targets offset
        if not self._start_loudness_worker(
            mode="relative",
            wav_path=wav_path,
            delta_i=delta_lufs,
            target_tp=-1.0,
        ):
            self._hide_busy()
            self.adjust_volume_btn.setEnabled(True)
            self.increase_lufs_btn.setEnabled(True)
            self.decrease_lufs_btn.setEnabled(True)
            QMessageBox.warning(self, "Busy", "Another loudness task is already running.")

    def _prepare_loudness_edit(self):
        """Stop playback and release media handles before loudnorm writes"""
        try:
            # Stop timers to avoid re-arming during edit
            self.position_timer.stop()
            self.loop_timer.stop()

            # Stop playback and clear media to release file handles
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())

            # Small delay helps Windows release file locks from the media backend
            QCoreApplication.processEvents()
            import time
            time.sleep(0.15)

            # Remember previous playing state if we want to resume later (unused for now)
            self._was_playing_before_loudnorm = was_playing
        except Exception as e:
            logging.warning(f"Failed to fully release media before loudnorm: {e}")
    
    def _read_scd_volume_float(self):
        """Read the current SCD volume float from the file and update the UI"""
        try:
            scd_path = getattr(self.loop_manager, "original_scd_path", None) or getattr(self.loop_manager, "current_file_path", None)
            if not scd_path or not Path(scd_path).exists() or Path(scd_path).suffix.lower() != ".scd":
                self.scd_volume_spinbox.setEnabled(False)
                self.apply_scd_volume_btn.setEnabled(False)
                self.scd_volume_status.setText("(No SCD file)")
                return
            
            import struct
            data = Path(scd_path).read_bytes()
            
            if len(data) < 0x54:
                self.scd_volume_status.setText("(Invalid SCD)")
                return
            
            table_off = int.from_bytes(data[0x50:0x54], 'little')
            if table_off <= 0 or table_off + 12 > len(data):
                self.scd_volume_status.setText("(Invalid offset)")
                return
            
            volume_pos = table_off + 8
            current_gain = struct.unpack('<f', data[volume_pos:volume_pos + 4])[0]
            
            # Update spinbox with current value
            self.scd_volume_spinbox.blockSignals(True)
            self.scd_volume_spinbox.setValue(current_gain)
            self.scd_volume_spinbox.blockSignals(False)
            
            self.scd_volume_spinbox.setEnabled(True)
            self.apply_scd_volume_btn.setEnabled(True)
            self.scd_volume_status.setText(f"(Current: {current_gain:.2f})")
            
        except Exception as e:
            logging.warning(f"Failed to read SCD volume float: {e}")
            self.scd_volume_status.setText("(Read error)")
            self.scd_volume_spinbox.setEnabled(False)
            self.apply_scd_volume_btn.setEnabled(False)
    
    def apply_scd_volume_float(self):
        """Apply the volume float value to the SCD file"""
        try:
            scd_path = getattr(self.loop_manager, "original_scd_path", None) or getattr(self.loop_manager, "current_file_path", None)
            if not scd_path or not Path(scd_path).exists() or Path(scd_path).suffix.lower() != ".scd":
                QMessageBox.warning(self, "Error", "No SCD file available to patch")
                return
            
            target_gain = self.scd_volume_spinbox.value()
            
            # Use the loop manager's patch method
            success = self.loop_manager._patch_scd_volume(scd_path, target_gain=target_gain)
            
            if success:
                self.scd_volume_status.setText(f"✓ Applied: {target_gain:.2f}")
                self.scd_volume_status.setStyleSheet("color: #4a8a4a; font-size: 9px; font-style: italic;")
                
                # Show success toast
                if hasattr(self, 'show_toast'):
                    self.show_toast(f"SCD volume float updated to {target_gain:.2f}", duration=2000)
                
                # Reset status color after 3 seconds
                QTimer.singleShot(3000, lambda: self.scd_volume_status.setStyleSheet("color: #888; font-size: 9px; font-style: italic;"))
            else:
                self.scd_volume_status.setText("✗ Failed")
                self.scd_volume_status.setStyleSheet("color: #8a4a4a; font-size: 9px; font-style: italic;")
                QMessageBox.warning(self, "Error", "Failed to patch SCD volume float")
                
        except Exception as e:
            logging.error(f"Failed to apply SCD volume float: {e}")
            self.scd_volume_status.setText("✗ Error")
            self.scd_volume_status.setStyleSheet("color: #8a4a4a; font-size: 9px; font-style: italic;")
            QMessageBox.warning(self, "Error", f"Failed to patch SCD volume: {str(e)}")
    
    def custom_volume_adjustment(self):
        """Open custom volume adjustment dialog"""
        self._apply_volume_adjustment("custom")
    
    def reset_volume_adjustment(self):
        """Reset audio to original volume levels"""
        if not self._volume_adjusted or self._original_audio_data is None:
            return
        
        reply = QMessageBox.question(
            self,
            "Reset Volume",
            "Reset audio to original volume levels?\n\nThis will undo all volume adjustments.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Restore original audio data
            self.waveform.audio_data = self._original_audio_data.copy()
            self._volume_adjusted = False
            
            # Disable reset button
            self.reset_volume_btn.setEnabled(False)
            
            # Update waveform display
            self.waveform.update_waveform()
            self.waveform.update()
            
            # Re-analyze audio to show original levels
            QTimer.singleShot(100, self.analyze_audio)
            
            logging.info("Volume reset to original levels")
    
    def _apply_volume_adjustment(self, method: str):
        """Apply volume adjustment using the specified method"""
        if self.waveform.audio_data is None or len(self.waveform.audio_data) == 0:
            QMessageBox.warning(self, "No Audio", "No audio data available for volume adjustment")
            return
        
        try:
            # Initialize audio analyzer
            analyzer = AudioAnalyzer()
            
            # Analyze current audio before adjustment
            original_levels = analyzer.analyze_audio_levels(
                self.waveform.audio_data, 
                self.waveform.sample_rate
            )
            
            # Apply the appropriate normalization
            if method == "auto":
                adjustment = analyzer.auto_level_adjustment(self.waveform.audio_data)
            elif method == "peak":
                adjustment = analyzer.normalize_peak(self.waveform.audio_data, target_db=-0.2)
            elif method == "rms":
                adjustment = analyzer.normalize_rms(self.waveform.audio_data, target_db=-15.0)
            elif method == "custom":
                # Open custom volume dialog
                dialog = CustomVolumeDialog(original_levels, self)
                if dialog.exec_() != QDialog.Accepted:
                    return  # User cancelled
                
                settings = dialog.get_settings()
                if settings['method'] == 'peak':
                    adjustment = analyzer.normalize_peak(self.waveform.audio_data, target_db=settings['target_db'])
                else:  # RMS
                    adjustment = analyzer.normalize_rms(self.waveform.audio_data, target_db=settings['target_db'])
            else:
                raise ValueError(f"Unknown volume adjustment method: {method}")
            
            # Ask user for confirmation
            adjustment_info = adjustment.to_dict()
            
            message = f"Volume Adjustment Preview:\n\n"
            for key, value in adjustment_info.items():
                message += f"{key}: {value}\n"
            
            message += f"\nThis will modify the audio in memory only.\n"
            message += f"To save changes, you must export/save the file.\n\n"
            message += f"Continue with volume adjustment?"
            
            reply = QMessageBox.question(
                self, 
                "Confirm Volume Adjustment", 
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Apply the adjustment
                self.waveform.audio_data = adjustment.adjusted_audio.copy()
                
                # Mark that volume has been adjusted
                self._volume_adjusted = True
                
                # Enable reset button
                self.reset_volume_btn.setEnabled(True)
                
                # Immediately write volume changes to WAV file for playback
                if self._write_volume_to_wav_immediately():
                    logging.info("Volume changes written to WAV file for immediate playback")
                
                # Update the waveform display
                self.waveform.update_waveform()
                self.waveform.update()
                
                # Force media player to recognize volume changes for immediate playback
                self._force_media_refresh()
                
                # Run analysis again to show new levels
                QTimer.singleShot(100, self.analyze_audio)
                
                # Show success message
                success_msg = f"Volume adjustment applied successfully!\n\n"
                success_msg += f"Method: {adjustment.normalization_type}\n"
                success_msg += f"Gain Applied: {adjustment.gain_applied_db:+.1f} dB\n"
                if adjustment.clipping_prevented:
                    success_msg += f"Note: Gain was reduced to prevent clipping."
                
                QMessageBox.information(self, "Volume Adjusted", success_msg)
                
                logging.info(f"Volume adjustment applied: {adjustment.normalization_type}, "
                           f"Gain: {adjustment.gain_applied_db:+.1f}dB")
            
        except Exception as e:
            logging.error(f"Error during volume adjustment: {e}")
            QMessageBox.critical(self, "Volume Adjustment Error", 
                               f"Failed to adjust volume: {str(e)}")
    
    def _update_volume_buttons_state(self):
        """Update the enabled state of volume adjustment buttons"""
        has_audio = (self.waveform.audio_data is not None and 
                    len(self.waveform.audio_data) > 0)
        
        self.adjust_volume_btn.setEnabled(has_audio)
        self.increase_lufs_btn.setEnabled(has_audio)
        self.decrease_lufs_btn.setEnabled(has_audio)
        # Reset button only enabled if volume was adjusted
        self.reset_volume_btn.setEnabled(has_audio and self._volume_adjusted)
    
    def showEvent(self, event):
        """Handle dialog show event to ensure proper initialization"""
        super().showEvent(event)
        # Ensure waveform is properly initialized when dialog becomes visible
        if hasattr(self, 'waveform') and hasattr(self.waveform, 'audio_data'):
            QTimer.singleShot(50, self._finalize_waveform_setup)

# Test function
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Mock loop manager for testing
    class MockLoopManager:
        def get_wav_path(self):
            return "test.wav"  # Replace with actual test file
        
        def get_file_info(self):
            return {
                'sample_rate': 44100,
                'total_samples': 1000000,
                'has_loop': False
            }
        
        def get_loop_points(self):
            return (0, 0)
        
        def set_loop_points(self, start, end):
            return True
        
        def clear_loop_points(self):
            return True
    
    mock_manager = MockLoopManager()
    dialog = LoopEditorDialog(mock_manager)
    dialog.show()
    
    sys.exit(app.exec_())
