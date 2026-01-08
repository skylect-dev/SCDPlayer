from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QRadioButton,
    QDoubleSpinBox,
    QLabel,
    QDialogButtonBox,
    QHBoxLayout,
)


class CustomVolumeDialog(QDialog):
    """Simple dialog to choose volume normalization settings"""

    def __init__(self, current_levels, parent=None):
        super().__init__(parent)
        self.current_levels = current_levels
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Custom Volume Adjustment")
        self.setModal(True)
        self.resize(420, 260)

        layout = QVBoxLayout(self)

        # Current levels display (optional)
        current_group = QGroupBox("Current Audio Levels")
        current_layout = QVBoxLayout(current_group)
        if self.current_levels is not None:
            lines = [
                f"Peak: {self.current_levels.peak_db:.1f} dB",
                f"RMS: {self.current_levels.rms_db:.1f} dB",
                f"Dynamic Range: {self.current_levels.dynamic_range_db:.1f} dB",
            ]
            current_info = QLabel("\n".join(lines))
        else:
            current_info = QLabel("No analysis available.")
        current_info.setStyleSheet("font-family: monospace; color: #ddd; padding: 6px;")
        current_layout.addWidget(current_info)
        layout.addWidget(current_group)

        # Method selection
        method_group = QGroupBox("Normalization Method")
        method_layout = QVBoxLayout(method_group)
        self.method_peak = QRadioButton("Peak normalization")
        self.method_rms = QRadioButton("RMS normalization")
        self.method_peak.setChecked(True)
        method_layout.addWidget(self.method_peak)
        method_layout.addWidget(self.method_rms)
        layout.addWidget(method_group)

        # Target value
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target (dB):"))
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(-60.0, 6.0)
        self.target_spin.setDecimals(1)
        self.target_spin.setSingleStep(0.1)
        self.target_spin.setValue(-0.2)  # Default peak target
        target_layout.addWidget(self.target_spin)
        target_layout.addStretch()
        layout.addLayout(target_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Wire method toggles
        self.method_peak.toggled.connect(self.update_recommended_value)
        self.method_rms.toggled.connect(self.update_recommended_value)

        # Style
        self.setStyleSheet(
            """
            QDialog { background-color: #2b2b2b; color: white; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #ddd;
                background-color: #2b2b2b;
            }
            QLabel { color: #ddd; }
            QPushButton {
                background-color: #404040;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                color: white;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #303030; }
            QDoubleSpinBox {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: white;
            }
            QRadioButton { color: #ddd; }
        """
        )

    def update_recommended_value(self):
        """Switch target defaults when method changes"""
        if self.method_peak.isChecked():
            self.target_spin.setValue(-0.2)
        else:
            self.target_spin.setValue(-15.0)

    def get_settings(self):
        return {
            "method": "peak" if self.method_peak.isChecked() else "rms",
            "target_db": self.target_spin.value(),
        }
