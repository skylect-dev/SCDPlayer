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
    QTreeView {
        outline: 0;
        show-decoration-selected: 1;
    }
    QTreeView::item:selected {
        border: none;
    }
    QTreeWidget {
        outline: 0;
        show-decoration-selected: 1;
    }
    QTreeWidget::item:selected {
        border: none;
    }
    QListWidget {
        outline: 0;
    }
    QListWidget::item:selected {
        border: none;
    }
    QMenuBar {
        background: #202020;
        color: #ffffff;
        border-bottom: 1px solid #404040;
    }
    QMenuBar::item {
        background: transparent;
        padding: 6px 12px;
    }
    QMenuBar::item:selected {
        background: #505050;
        color: #ffffff;
    }
    QMenuBar::item:pressed {
        background: #0078d4;
    }
    QMenu {
        background: #2c2c2c;
        border: 1px solid #404040;
        color: #ffffff;
    }
    QMenu::item {
        padding: 6px 24px;
    }
    QMenu::item:selected {
        background: #0078d4;
    }
    /* Scrollbar Styling */
    QScrollBar:vertical {
        background: transparent;
        width: 14px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #404040;
        min-height: 30px;
        border-radius: 4px;
        margin: 3px;
    }
    QScrollBar::handle:vertical:hover {
        background: #505050;
    }
    QScrollBar::handle:vertical:pressed {
        background: #0078d4;
    }
    QScrollBar::add-line:vertical {
        height: 0px;
    }
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QScrollBar:horizontal {
        background: transparent;
        height: 14px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #404040;
        min-width: 30px;
        border-radius: 4px;
        margin: 3px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #505050;
    }
    QScrollBar::handle:horizontal:pressed {
        background: #0078d4;
    }
    QScrollBar::add-line:horizontal {
        width: 0px;
    }
    QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
    }
'''

# Reusable button styles (loop editor and dialogs)
BUTTON_PRIMARY_BLUE = """
    QPushButton {
        background-color: #2060c0;
        border: 1px solid #4080ff;
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: bold;
        color: white;
        min-width: 60px;
    }
    QPushButton:hover { background-color: #3070d0; }
    QPushButton:pressed { background-color: #1050a0; }
"""

BUTTON_SECONDARY_DARK = """
    QPushButton {
        background-color: #404040;
        border: 1px solid #666;
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
        color: white;
        min-width: 60px;
    }
    QPushButton:hover { background-color: #505050; }
    QPushButton:pressed { background-color: #303030; }
"""

BUTTON_TOGGLE_LOOP = """
    QPushButton {
        background-color: #404040;
        border: 1px solid #666;
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
        color: white;
        min-width: 80px;
    }
    QPushButton:hover { background-color: #505050; }
    QPushButton:pressed { background-color: #303030; }
    QPushButton:checked {
        background-color: #c06020;
        border-color: #ff8040;
        color: white;
    }
"""

BUTTON_CLEAR_DARK = """
    QPushButton {
        background-color: #404040;
        border: 2px solid #666;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
        color: white;
    }
    QPushButton:hover {
        background-color: #505050;
        border-color: #777;
    }
    QPushButton:pressed {
        background-color: #303030;
    }
"""

BUTTON_CANCEL_DANGER = """
    QPushButton {
        background-color: #604040;
        border: 2px solid #806060;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
        color: white;
    }
    QPushButton:hover {
        background-color: #705050;
        border-color: #907070;
    }
    QPushButton:pressed {
        background-color: #503030;
    }
"""

BUTTON_VOLUME_GREEN = """
    QPushButton {
        background-color: #2a5a2a;
        border: 1px solid #4a8a4a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: bold;
        color: white;
    }
    QPushButton:hover { background-color: #3a6a3a; }
    QPushButton:pressed { background-color: #1a4a1a; }
    QPushButton:disabled {
        background-color: #333;
        border-color: #555;
        color: #888;
    }
"""

BUTTON_VOLUME_RESET = """
    QPushButton {
        background-color: #5a2a2a;
        border: 1px solid #8a4a4a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: bold;
        color: white;
    }
    QPushButton:hover { background-color: #6a3a3a; }
    QPushButton:pressed { background-color: #4a1a1a; }
    QPushButton:disabled {
        background-color: #333;
        border-color: #555;
        color: #888;
    }
"""

BUTTON_APPLY_SCD = """
    QPushButton {
        background-color: #2a4a5a;
        border: 1px solid #4a6a8a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: bold;
        color: white;
    }
    QPushButton:hover { background-color: #3a5a6a; }
    QPushButton:pressed { background-color: #1a3a4a; }
    QPushButton:disabled {
        background-color: #333;
        border-color: #555;
        color: #888;
    }
"""
