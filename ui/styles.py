"""Application styles and constants"""

# Main application stylesheet
DARK_THEME = '''
    QWidget {
        background: #23272e;
        color: #f0f0f0;
        font-size: 14px;
    }
    QPushButton {
        background: #353b45;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 6px 16px;
        color: #f0f0f0;
    }
    QPushButton:hover {
        background: #3e4550;
    }
    QPushButton:pressed {
        background: #2a2f36;
    }
    QPushButton:disabled {
        background: #23272e;
        color: #888;
    }
    QSlider::groove:horizontal {
        height: 6px;
        background: #444;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #f0f0f0;
        border: 1px solid #888;
        width: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }
    QGroupBox {
        font-weight: bold;
        border: 2px solid #444;
        border-radius: 5px;
        margin-top: 1ex;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    QListWidget {
        background: #2a2f36;
        border: 1px solid #444;
        border-radius: 3px;
    }
    QListWidget::item {
        padding: 3px;
        border-bottom: 1px solid #333;
    }
    QListWidget::item:selected {
        background: #3e4550;
    }
    QListWidget::item:hover {
        background: #35393f;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }
    QCheckBox::indicator:unchecked {
        background: #2a2f36;
        border: 1px solid #444;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background: #3e4550;
        border: 1px solid #666;
        border-radius: 3px;
    }
'''
