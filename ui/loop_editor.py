"""
Loop Editor Widget for SCD files - Clean Phase 1 Implementation

This provides the UI for loop point editing with:
- Sample-accurate controls
- Time/sample conversion
- Visual feedback
- Clean integration with LoopPointManager

Phase 1: Display and edit only - no saving functionality yet
"""
import logging
from typing import Optional
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
                           QCheckBox, QMessageBox)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont
from core.loop_manager import LoopPointManager


class LoopEditor(QWidget):
    """
    Loop point editor widget for SCD files
    
    Phase 1 Features:
    - Display existing loop points from vgmstream
    - Sample-accurate editing controls
    - Time ↔ Sample conversion
    - Input validation
    - Clean integration with audio playback
    
    Future Phases:
    - Phase 2+: Save functionality with codec awareness
    """
    
    # Signals
    loop_points_changed = pyqtSignal(int, int)  # start_sample, end_sample
    play_from_position = pyqtSignal(float)      # time in seconds
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop_manager = LoopPointManager()
        self.is_updating = False  # Prevent recursive updates
        
        self.setup_ui()
        self.connect_signals()
        
        # Update timer for real-time feedback
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.setSingleShot(True)
        
    def setup_ui(self):
        """Set up the loop editor user interface"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Loop Point Editor")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # File info group
        self.file_info_group = QGroupBox("File Information")
        file_info_layout = QVBoxLayout(self.file_info_group)
        
        self.file_path_label = QLabel("No file loaded")
        self.file_info_label = QLabel("Sample Rate: -- | Total Samples: --")
        self.loop_status_label = QLabel("Loop Points: Not detected")
        
        file_info_layout.addWidget(self.file_path_label)
        file_info_layout.addWidget(self.file_info_label)
        file_info_layout.addWidget(self.loop_status_label)
        
        layout.addWidget(self.file_info_group)
        
        # Loop points group
        self.loop_group = QGroupBox("Loop Points")
        loop_layout = QVBoxLayout(self.loop_group)
        
        # Enable/disable loop
        self.loop_enabled_checkbox = QCheckBox("Enable Loop Points")
        self.loop_enabled_checkbox.setChecked(False)
        loop_layout.addWidget(self.loop_enabled_checkbox)
        
        # Loop start controls
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Loop Start:"))
        
        self.start_sample_spin = QSpinBox()
        self.start_sample_spin.setMinimum(0)
        self.start_sample_spin.setMaximum(999999999)
        self.start_sample_spin.setSuffix(" samples")
        start_layout.addWidget(self.start_sample_spin)
        
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setMinimum(0.0)
        self.start_time_spin.setMaximum(99999.999)
        self.start_time_spin.setDecimals(3)
        self.start_time_spin.setSuffix(" sec")
        start_layout.addWidget(self.start_time_spin)
        
        self.play_start_btn = QPushButton("▶ Play from Start")
        self.play_start_btn.setMaximumWidth(120)
        start_layout.addWidget(self.play_start_btn)
        
        loop_layout.addLayout(start_layout)
        
        # Loop end controls
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("Loop End:  "))
        
        self.end_sample_spin = QSpinBox()
        self.end_sample_spin.setMinimum(1)
        self.end_sample_spin.setMaximum(999999999)
        self.end_sample_spin.setSuffix(" samples")
        end_layout.addWidget(self.end_sample_spin)
        
        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setMinimum(0.001)
        self.end_time_spin.setMaximum(99999.999)
        self.end_time_spin.setDecimals(3)
        self.end_time_spin.setSuffix(" sec")
        end_layout.addWidget(self.end_time_spin)
        
        self.play_end_btn = QPushButton("▶ Play from End")
        self.play_end_btn.setMaximumWidth(120)
        end_layout.addWidget(self.play_end_btn)
        
        loop_layout.addLayout(end_layout)
        
        # Loop info
        self.loop_info_label = QLabel("Loop Duration: --")
        loop_layout.addWidget(self.loop_info_label)
        
        layout.addWidget(self.loop_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("Apply Loop Points")
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)
        
        self.clear_btn = QPushButton("Clear Loop Points")
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)
        
        # Phase 1: Save is disabled
        self.save_btn = QPushButton("Save to SCD (Phase 2+)")
        self.save_btn.setEnabled(False)
        self.save_btn.setToolTip("Loop point saving will be implemented in Phase 2 with codec detection")
        button_layout.addWidget(self.save_btn)
        
        layout.addWidget(QWidget())  # Spacer
        layout.addLayout(button_layout)
        
        # Initially disable all controls
        self.set_controls_enabled(False)
        
    def connect_signals(self):
        """Connect UI signals to handlers"""
        # Loop enable/disable
        self.loop_enabled_checkbox.toggled.connect(self._on_loop_enabled_changed)
        
        # Sample spinboxes
        self.start_sample_spin.valueChanged.connect(self._on_start_sample_changed)
        self.end_sample_spin.valueChanged.connect(self._on_end_sample_changed)
        
        # Time spinboxes
        self.start_time_spin.valueChanged.connect(self._on_start_time_changed)
        self.end_time_spin.valueChanged.connect(self._on_end_time_changed)
        
        # Play buttons
        self.play_start_btn.clicked.connect(self._play_from_start)
        self.play_end_btn.clicked.connect(self._play_from_end)
        
        # Action buttons
        self.apply_btn.clicked.connect(self._apply_loop_points)
        self.clear_btn.clicked.connect(self._clear_loop_points)
        self.save_btn.clicked.connect(self._save_loop_points)
        
    def load_file(self, file_path: str, sample_rate: int, total_samples: int):
        """Load a file for loop editing"""
        logging.info(f"Loop editor loading file: {file_path}")
        
        # Set context in loop manager
        self.loop_manager.set_file_context(file_path, sample_rate, total_samples)
        
        # Try to read existing loop points
        has_loops = False
        if file_path.lower().endswith('.scd'):
            has_loops = self.loop_manager.read_loop_metadata_from_scd(file_path)
        
        # Update UI
        self._update_file_info(file_path, sample_rate, total_samples, has_loops)
        self._update_controls_from_manager()
        
        # Enable controls
        self.set_controls_enabled(True)
        
    def _update_file_info(self, file_path: str, sample_rate: int, total_samples: int, has_loops: bool):
        """Update file information display"""
        from pathlib import Path
        filename = Path(file_path).name
        
        self.file_path_label.setText(f"File: {filename}")
        self.file_info_label.setText(f"Sample Rate: {sample_rate:,} Hz | Total Samples: {total_samples:,}")
        
        if has_loops:
            start, end = self.loop_manager.get_loop_samples()
            self.loop_status_label.setText(f"Loop Points: {start:,} → {end:,} samples")
        else:
            self.loop_status_label.setText("Loop Points: Not detected")
            
        # Update spinbox limits
        self.start_sample_spin.setMaximum(total_samples - 1)
        self.end_sample_spin.setMaximum(total_samples)
        
        if sample_rate > 0:
            max_time = total_samples / sample_rate
            self.start_time_spin.setMaximum(max_time)
            self.end_time_spin.setMaximum(max_time)
        
    def _update_controls_from_manager(self):
        """Update UI controls from loop manager state"""
        self.is_updating = True
        
        if self.loop_manager.has_loop_points():
            start, end = self.loop_manager.get_loop_samples()
            start_time, end_time = self.loop_manager.get_loop_times()
            
            self.loop_enabled_checkbox.setChecked(True)
            self.start_sample_spin.setValue(start)
            self.end_sample_spin.setValue(end)
            self.start_time_spin.setValue(start_time)
            self.end_time_spin.setValue(end_time)
            
            self._update_loop_info(start, end, start_time, end_time)
        else:
            self.loop_enabled_checkbox.setChecked(False)
            self.start_sample_spin.setValue(0)
            self.end_sample_spin.setValue(1000)  # Default small loop
            self.start_time_spin.setValue(0.0)
            self.end_time_spin.setValue(0.023)  # ~1000 samples at 44.1kHz
            
            self.loop_info_label.setText("Loop Duration: --")
        
        self.is_updating = False
        self._update_button_states()
        
    def _update_loop_info(self, start_sample: int, end_sample: int, start_time: float, end_time: float):
        """Update loop duration info"""
        loop_samples = end_sample - start_sample
        loop_time = end_time - start_time
        self.loop_info_label.setText(f"Loop Duration: {loop_samples:,} samples ({loop_time:.3f} sec)")
        
    def _on_loop_enabled_changed(self, enabled: bool):
        """Handle loop enable/disable"""
        if self.is_updating:
            return
            
        self.set_loop_controls_enabled(enabled)
        
        if enabled:
            self._apply_loop_points()
        else:
            self._clear_loop_points()
            
    def _on_start_sample_changed(self, value: int):
        """Handle start sample change"""
        if self.is_updating:
            return
            
        # Update corresponding time
        if self.loop_manager.sample_rate > 0:
            time_value = value / self.loop_manager.sample_rate
            self.is_updating = True
            self.start_time_spin.setValue(time_value)
            self.is_updating = False
            
        self._schedule_update()
        
    def _on_end_sample_changed(self, value: int):
        """Handle end sample change"""
        if self.is_updating:
            return
            
        # Update corresponding time
        if self.loop_manager.sample_rate > 0:
            time_value = value / self.loop_manager.sample_rate
            self.is_updating = True
            self.end_time_spin.setValue(time_value)
            self.is_updating = False
            
        self._schedule_update()
        
    def _on_start_time_changed(self, value: float):
        """Handle start time change"""
        if self.is_updating:
            return
            
        # Update corresponding sample
        if self.loop_manager.sample_rate > 0:
            sample_value = int(value * self.loop_manager.sample_rate)
            self.is_updating = True
            self.start_sample_spin.setValue(sample_value)
            self.is_updating = False
            
        self._schedule_update()
        
    def _on_end_time_changed(self, value: float):
        """Handle end time change"""
        if self.is_updating:
            return
            
        # Update corresponding sample
        if self.loop_manager.sample_rate > 0:
            sample_value = int(value * self.loop_manager.sample_rate)
            self.is_updating = True
            self.end_sample_spin.setValue(sample_value)
            self.is_updating = False
            
        self._schedule_update()
        
    def _schedule_update(self):
        """Schedule a delayed update to avoid excessive processing"""
        self.update_timer.start(100)  # 100ms delay
        
    def _update_display(self):
        """Update display after changes"""
        if self.is_updating:
            return
            
        start_sample = self.start_sample_spin.value()
        end_sample = self.end_sample_spin.value()
        start_time = self.start_time_spin.value()
        end_time = self.end_time_spin.value()
        
        self._update_loop_info(start_sample, end_sample, start_time, end_time)
        self._update_button_states()
        
    def _play_from_start(self):
        """Play from loop start position"""
        start_time = self.start_time_spin.value()
        self.play_from_position.emit(start_time)
        
    def _play_from_end(self):
        """Play from loop end position"""
        end_time = self.end_time_spin.value()
        self.play_from_position.emit(end_time)
        
    def _apply_loop_points(self):
        """Apply current loop point settings"""
        start_sample = self.start_sample_spin.value()
        end_sample = self.end_sample_spin.value()
        
        if self.loop_manager.set_loop_points(start_sample, end_sample):
            self.loop_points_changed.emit(start_sample, end_sample)
            self._update_button_states()
            logging.info(f"Applied loop points: {start_sample} → {end_sample}")
        else:
            QMessageBox.warning(self, "Invalid Loop Points", 
                              "Loop points are invalid. Please check your values.")
            
    def _clear_loop_points(self):
        """Clear loop points"""
        self.loop_manager.clear_loop_points()
        self.loop_enabled_checkbox.setChecked(False)
        self.loop_points_changed.emit(0, 0)  # Signal no loop
        self._update_button_states()
        logging.info("Cleared loop points")
        
    def _save_loop_points(self):
        """Save loop points to SCD file (Phase 2+ feature)"""
        QMessageBox.information(self, "Feature Not Available", 
                              "Loop point saving will be implemented in Phase 2 with codec detection.\n\n"
                              "Phase 1 focuses on reading and editing loop points only.")
        
    def _update_button_states(self):
        """Update button enabled/disabled states"""
        has_loop = self.loop_manager.has_loop_points()
        has_file = self.loop_manager.current_file_path is not None
        
        self.apply_btn.setEnabled(has_file and self.loop_enabled_checkbox.isChecked())
        self.clear_btn.setEnabled(has_loop)
        # save_btn stays disabled in Phase 1
        
    def set_controls_enabled(self, enabled: bool):
        """Enable/disable all controls"""
        self.loop_group.setEnabled(enabled)
        self.set_loop_controls_enabled(enabled and self.loop_enabled_checkbox.isChecked())
        
    def set_loop_controls_enabled(self, enabled: bool):
        """Enable/disable loop editing controls"""
        controls = [
            self.start_sample_spin, self.start_time_spin, self.play_start_btn,
            self.end_sample_spin, self.end_time_spin, self.play_end_btn
        ]
        
        for control in controls:
            control.setEnabled(enabled)
            
        self._update_button_states()
