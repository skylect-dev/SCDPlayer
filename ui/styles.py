"""Application styles and constants"""

# Main application stylesheet - Windows 11 Theme
DARK_THEME = '''
    QWidget {
        background: #202020;
        color: #ffffff;
        font-size: 14px;
        font-family: "Segoe UI", sans-serif;
    }
    QPushButton {
        background: #323232;
        border: 1px solid #404040;
        border-radius: 6px;
        padding: 8px 16px;
        color: #ffffff;
        font-weight: 400;
    }
    QPushButton:hover {
        background: #404040;
        border: 1px solid #505050;
    }
    QPushButton:pressed {
        background: #2a2a2a;
        border: 1px solid #303030;
    }
    QPushButton:disabled {
        background: #1a1a1a;
        color: #666666;
        border: 1px solid #2a2a2a;
    }
    QSlider::groove:horizontal {
        height: 4px;
        background: #404040;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #0078d4;
        border: 1px solid #005a9e;
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }
    QSlider::handle:horizontal:hover {
        background: #106ebe;
    }
    QGroupBox {
        font-weight: 600;
        border: 1px solid #404040;
        border-radius: 6px;
        margin-top: 1ex;
        padding-top: 12px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px 0 8px;
    }
    QListWidget {
        background: #2c2c2c;
        border: 1px solid #404040;
        border-radius: 6px;
        selection-background-color: #0078d4;
    }
    QListWidget::item {
        padding: 6px;
        border-bottom: 1px solid #353535;
        border-radius: 3px;
    }
    QListWidget::item:selected {
        background: #0078d4;
        color: white;
    }
    QListWidget::item:hover {
        background: #383838;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }
    QCheckBox::indicator:unchecked {
        background: #2c2c2c;
        border: 1px solid #404040;
        border-radius: 4px;
    }
    QCheckBox::indicator:checked {
        background: #0078d4;
        border: 1px solid #005a9e;
        border-radius: 4px;
        image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMMTEgNEw1IDEwTDEgNkwyIDVMNSA4TDEwIDNaIiBmaWxsPSJ3aGl0ZSIvPgo8L3N2Zz4K);
    }
    QComboBox {
        background: #323232;
        border: 1px solid #404040;
        border-radius: 6px;
        padding: 6px 12px;
        color: #ffffff;
    }
    QComboBox:hover {
        border: 1px solid #0078d4;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox::down-arrow {
        image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNiIgdmlld0JveD0iMCAwIDEwIDYiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik01IDZMMCAwSDEwTDUgNloiIGZpbGw9IndoaXRlIi8+Cjwvc3ZnPgo=);
    }
    QComboBox QAbstractItemView {
        background: #323232;
        border: 1px solid #404040;
        selection-background-color: #0078d4;
        border-radius: 6px;
    }
'''
