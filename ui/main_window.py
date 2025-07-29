"""Streamlined main application window for SCDPlayer"""
import os
import tempfile
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, 
    QLabel, QSlider, QSizePolicy, QListWidget, QCheckBox, QMessageBox, 
    QSplitter, QGroupBox, QProgressBar, QComboBox, QDialog, QShortcut,
    QMenuBar, QAction, QApplication, QScrollArea, QFrame, QListWidgetItem,
    QLineEdit
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QKeySequence, QCursor

from version import __version__
from ui.widgets import ScrollingLabel, create_icon, create_app_icon
from ui.styles import DARK_THEME
from ui.dialogs import show_themed_message, show_themed_file_dialog, apply_title_bar_theming
from ui.conversion_manager import ConversionManager
from ui.kh_rando_manager import KHRandoManager
from ui.help_dialog import HelpDialog
from ui.loop_editor_dialog import LoopEditorDialog
from core.loop_manager import HybridLoopManager
from core.converter import AudioConverter
from core.threading import FileLoadThread
from core.library import AudioLibrary
from core.kh_rando import KHRandoExporter
from utils.config import Config
from utils.helpers import format_time, send_to_recycle_bin
from utils.updater import AutoUpdater


class SCDPlayer(QMainWindow):
    """Main SCDPlayer application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDPlayer v{__version__}')
        self.setGeometry(100, 100, 1400, 850)
        
        # Initialize components
        self.config = Config()
        # Load settings early, before UI setup
        self.config.load_settings()
        
        self.converter = AudioConverter()
        self.kh_rando_exporter = KHRandoExporter(self)
        self.current_file = None
        self.current_playlist_index = -1
        self.playlist = []
        
        # Initialize UI components
        self.setup_menu_bar()
        self.setup_ui()
        self.setup_media_player()
        
        # Initialize managers after UI is created
        self.conversion_manager = ConversionManager(self)
        self.kh_rando_manager = KHRandoManager(self)
        self.loop_manager = HybridLoopManager()
        self.auto_updater = AutoUpdater(self)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Set window icon and style
        self.setWindowIcon(create_app_icon())
        self.setup_title_bar_theming()
        self.setStyleSheet(DARK_THEME)
        
        # Threading components
        self.file_load_thread = None
    
    def setup_menu_bar(self):
        """Setup the application menu bar"""
        menubar = self.menuBar()
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        help_action = QAction('&Help Guide', self)
        help_action.setShortcut('F1')
        help_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(help_action)
        
        help_menu.addSeparator()
        
        check_updates_action = QAction('Check for &Updates', self)
        check_updates_action.triggered.connect(self.check_for_updates_manual)
        help_menu.addAction(check_updates_action)
        
    def show_help_dialog(self):
        """Show the help dialog"""
        help_dialog = HelpDialog(self)
        help_dialog.exec_()
        
    def check_for_updates_startup(self):
        """Check for updates silently on startup"""
        if hasattr(self, 'auto_updater'):
            self.auto_updater.check_for_updates(silent=True)
    
    def check_for_updates_manual(self):
        """Manually check for updates (show result)"""
        if hasattr(self, 'auto_updater'):
            self.auto_updater.check_for_updates(silent=False)
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create main widget and splitter
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        
        # Create splitter for player and library
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Player controls
        player_panel = self.create_player_panel()
        splitter.addWidget(player_panel)
        
        # Right panel - Library
        library_panel = self.create_library_panel()
        splitter.addWidget(library_panel)
        
        # Set splitter sizes
        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
    
    def create_player_panel(self):
        """Create the left player controls panel"""
        player_panel = QWidget()
        player_panel.setFixedWidth(450)
        player_layout = QVBoxLayout()
        player_layout.setSpacing(8)
        
        # File info (at the top)
        info_layout = QHBoxLayout()
        self.label = ScrollingLabel('No file loaded')
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        info_layout.addWidget(self.label)

        self.time_label = QLabel('00:00 / 00:00')
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setFixedWidth(120)
        info_layout.addWidget(self.time_label)
        player_layout.addLayout(info_layout)
        
        # Seek bar
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        # Add state tracking for scrubbing
        self.is_playing_before_scrub = False
        self.is_scrubbing = False
        
        # Connect slider events for better scrubbing behavior
        self.seek_slider.sliderPressed.connect(self.on_scrub_start)
        self.seek_slider.sliderReleased.connect(self.on_scrub_end)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        player_layout.addWidget(self.seek_slider)

        # Playback controls - create a tightly grouped container
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setSpacing(5)  # Small spacing between buttons
        controls_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        
        self.prev_btn = self.create_control_button("previous", "Previous Track", self.previous_track)
        self.prev_btn.setFixedSize(45, 40)  # Make prev/next buttons wider
        # Combined play/pause button - starts as play button
        self.play_pause_btn = self.create_control_button("play", "Play", self.toggle_play_pause)
        self.play_pause_btn.setFixedSize(50, 40)  # Keep play/pause button wider
        self.next_btn = self.create_control_button("next", "Next Track", self.next_track)
        self.next_btn.setFixedSize(45, 40)  # Make prev/next buttons wider
        
        for btn in [self.prev_btn, self.play_pause_btn, self.next_btn]:
            controls_layout.addWidget(btn)
        
        # Add the controls container to the player layout
        player_layout.addWidget(controls_container, alignment=Qt.AlignCenter)
        player_layout.addSpacing(15)

        # Load controls
        load_layout = QHBoxLayout()
        self.load_file_btn = QPushButton('Load File')
        self.load_file_btn.clicked.connect(self.load_file)
        load_layout.addWidget(self.load_file_btn)
        player_layout.addLayout(load_layout)
        player_layout.addSpacing(15)

        # Metadata display area (after conversion buttons)
        self.metadata_label = QLabel("No file loaded")
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setStyleSheet("""
            QLabel {
                background-color: #111111;
                border: 1px solid #333;
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
                font-size: 11px;
            }
        """)
        self.metadata_label.setMinimumHeight(60)
        player_layout.addWidget(self.metadata_label)

        player_layout.addStretch()
        player_panel.setLayout(player_layout)
        return player_panel
    
    def create_control_button(self, icon_type, tooltip, callback):
        """Create a playback control button"""
        btn = QPushButton()
        btn.setIcon(create_icon(icon_type))
        btn.setText("")  # Ensure no text is set
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        btn.setEnabled(False)
        btn.setFixedSize(40, 40)
        return btn
    
    def create_library_panel(self):
        """Create the right library panel"""
        library_panel = QWidget()
        library_layout = QVBoxLayout()
        
        # Library header
        library_header = QGroupBox("Audio Library")
        header_layout = QVBoxLayout()
        
        # Folder controls
        folder_controls = QHBoxLayout()
        add_folder_btn = QPushButton('Add Folder')
        add_folder_btn.clicked.connect(self.add_library_folder)
        folder_controls.addWidget(add_folder_btn)
        
        remove_folder_btn = QPushButton('Remove Folder')
        remove_folder_btn.clicked.connect(self.remove_library_folder)
        self.remove_folder_btn = remove_folder_btn  # Store reference for enabling/disabling
        folder_controls.addWidget(remove_folder_btn)
        
        rescan_btn = QPushButton('Rescan')
        rescan_btn.clicked.connect(self.rescan_library)
        folder_controls.addWidget(rescan_btn)
        header_layout.addLayout(folder_controls)
        
        # Folder list
        header_layout.addWidget(QLabel('Scan Folders:'))
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(100)
        self.folder_list.itemSelectionChanged.connect(self.on_folder_selection_changed)
        # Populate folder list with saved folders on initial load
        for folder in self.config.library_folders:
            self.folder_list.addItem(folder)
        # Initially disable remove button if no selection
        self.remove_folder_btn.setEnabled(False)
        header_layout.addWidget(self.folder_list)

        # Scan subdirs toggle
        self.subdirs_checkbox = QCheckBox('Scan subdirectories')
        self.subdirs_checkbox.stateChanged.connect(self.toggle_subdirs)
        # Set checkbox state on initial load
        self.subdirs_checkbox.setChecked(self.config.scan_subdirs)
        header_layout.addWidget(self.subdirs_checkbox)
        
        # KH Rando folder controls
        kh_rando_layout = QHBoxLayout()
        kh_rando_layout.addWidget(QLabel('KH Rando Folder:'))
        
        self.kh_rando_path_label = QLabel('Not selected')
        self.kh_rando_path_label.setStyleSheet("color: gray; font-style: italic;")
        kh_rando_layout.addWidget(self.kh_rando_path_label)
        
        self.select_kh_rando_btn = QPushButton('Select KH Rando Folder')
        self.select_kh_rando_btn.clicked.connect(self.select_kh_rando_folder)
        kh_rando_layout.addWidget(self.select_kh_rando_btn)
        
        self.open_kh_rando_btn = QPushButton('Open Folder')
        self.open_kh_rando_btn.clicked.connect(self.open_kh_rando_folder)
        self.open_kh_rando_btn.setEnabled(False)  # Disabled until folder is set
        self.open_kh_rando_btn.setToolTip('Open the KH Rando folder in file explorer')
        kh_rando_layout.addWidget(self.open_kh_rando_btn)
        
        header_layout.addLayout(kh_rando_layout)

        library_header.setLayout(header_layout)
        library_layout.addWidget(library_header)

        # Create vertical splitter between header and file libraries
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setChildrenCollapsible(False)
        
        # The header is already added to library_layout, so we need to reorganize
        # Remove header from layout and add to splitter
        library_layout.removeWidget(library_header)
        main_splitter.addWidget(library_header)
        
        # === File Libraries Section (side by side) ===
        files_widget = QWidget()
        files_layout = QHBoxLayout()
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(5)
        
        # Create horizontal splitter for the two file libraries
        files_splitter = QSplitter(Qt.Horizontal)
        files_splitter.setChildrenCollapsible(False)
        
        # === Left: Regular Audio Files ===
        regular_files_widget = QWidget()
        regular_files_layout = QVBoxLayout()
        regular_files_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add search bar for regular files
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        search_container = QHBoxLayout()
        search_container.setContentsMargins(0, 0, 0, 0)
        search_container.setSpacing(0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files... (filename or folder)")
        self.search_input.textChanged.connect(self.filter_library_files)
        search_container.addWidget(self.search_input)
        
        self.clear_search_btn = QPushButton("×")
        self.clear_search_btn.clicked.connect(self.clear_search)
        self.clear_search_btn.setMaximumWidth(25)
        self.clear_search_btn.setMaximumHeight(25)
        self.clear_search_btn.setToolTip("Clear search")
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                border: 1px solid #666666;
                border-radius: 12px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                padding: 0px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #555555;
                border-color: #888888;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        search_container.addWidget(self.clear_search_btn)
        
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addLayout(search_container)
        
        regular_files_layout.addLayout(search_layout)
        
        # Organization options
        org_layout = QHBoxLayout()
        org_layout.setContentsMargins(0, 0, 0, 0)
        
        self.organize_by_folder_cb = QCheckBox("Group by folder")
        self.organize_by_folder_cb.stateChanged.connect(self.toggle_folder_organization)
        self.organize_by_folder_cb.setToolTip("Organize files by their originating folder")
        self.organize_by_folder_cb.setChecked(True)  # Default to checked
        org_layout.addWidget(self.organize_by_folder_cb)
        
        org_layout.addStretch()
        regular_files_layout.addLayout(org_layout)
        
        regular_files_layout.addWidget(QLabel('Audio Files (SCD, WAV, MP3, OGG, FLAC):'))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)  # Allow multiple selection
        self.file_list.itemDoubleClicked.connect(self.load_from_library)
        self.file_list.itemClicked.connect(self.on_library_item_clicked)  # Handle single clicks
        self.file_list.itemSelectionChanged.connect(self.on_library_selection_changed)
        regular_files_layout.addWidget(self.file_list)
        
        regular_files_widget.setLayout(regular_files_layout)
        files_splitter.addWidget(regular_files_widget)
        
        # === Right: KH Rando Files Section ===
        kh_rando_widget = QWidget()
        kh_rando_layout = QVBoxLayout()
        kh_rando_layout.setContentsMargins(0, 0, 0, 0)
        
        kh_rando_layout.addWidget(QLabel('KH Randomizer Files:'))
        
        # Create KH Rando file list - identical to main library structure
        self.kh_rando_file_list = QListWidget()
        self.kh_rando_file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.kh_rando_file_list.itemDoubleClicked.connect(self.load_from_library)
        self.kh_rando_file_list.itemClicked.connect(self.on_kh_rando_item_clicked)
        self.kh_rando_file_list.itemSelectionChanged.connect(self.on_kh_rando_selection_changed)
        
        # Create storage for KH Rando category tracking
        self.kh_rando_categories = {}
        self.kh_rando_category_states = {}
        from core.kh_rando import KHRandoExporter
        
        # Initialize category states (all expanded by default)
        for category_key, category_name in KHRandoExporter.MUSIC_CATEGORIES.items():
            self.kh_rando_categories[category_key] = category_name
            self.kh_rando_category_states[category_key] = True
        
        kh_rando_layout.addWidget(self.kh_rando_file_list)
        
        kh_rando_widget.setLayout(kh_rando_layout)
        files_splitter.addWidget(kh_rando_widget)
        
        # Set initial splitter sizes (50% regular files, 50% KH Rando)
        files_splitter.setSizes([300, 300])
        
        files_layout.addWidget(files_splitter)
        files_widget.setLayout(files_layout)
        
        # Add files widget to main splitter
        main_splitter.addWidget(files_widget)
        
        # Set initial sizes for header vs files (20% header, 80% files - smaller header by default)
        main_splitter.setSizes([150, 600])
        
        library_layout.addWidget(main_splitter)

        # Library management buttons
        library_buttons_layout = QHBoxLayout()
        
        self.export_selected_btn = QPushButton('Export Selected to KH Rando (E)')
        self.export_selected_btn.clicked.connect(self.export_selected_to_kh_rando)
        self.export_selected_btn.setEnabled(False)
        self.export_selected_btn.setToolTip('Export selected library files to Kingdom Hearts Randomizer music folder')
        library_buttons_layout.addWidget(self.export_selected_btn)
        
        self.export_missing_btn = QPushButton('Export Missing to KH Rando (M)')
        self.export_missing_btn.clicked.connect(self.export_missing_to_kh_rando)
        self.export_missing_btn.setToolTip('Export library files that are not in KH Rando folder')
        library_buttons_layout.addWidget(self.export_missing_btn)
        
        self.delete_selected_btn = QPushButton('Delete Selected (Del)')
        self.delete_selected_btn.clicked.connect(self.delete_selected_files)
        self.delete_selected_btn.setToolTip('Move selected files to Recycle Bin (DEL key shortcut)')
        self.delete_selected_btn.setEnabled(False)  # Disabled initially
        library_buttons_layout.addWidget(self.delete_selected_btn)
        
        self.open_file_location_btn = QPushButton('Open File Location (Ctrl+L)')
        self.open_file_location_btn.clicked.connect(self.open_file_location)
        self.open_file_location_btn.setToolTip('Open the folder containing the selected file or currently playing file in File Explorer (Ctrl+L)')
        self.open_file_location_btn.setEnabled(False)  # Disabled initially
        library_buttons_layout.addWidget(self.open_file_location_btn)
        
        library_layout.addLayout(library_buttons_layout)

        # Conversion buttons for library files
        convert_buttons_layout = QHBoxLayout()
        
        self.convert_to_wav_btn = QPushButton('Convert Selected to WAV (W)')
        self.convert_to_wav_btn.clicked.connect(self.convert_selected_to_wav)
        self.convert_to_wav_btn.setEnabled(False)  # Disabled initially
        self.convert_to_wav_btn.setToolTip('Convert selected library files to WAV format')
        convert_buttons_layout.addWidget(self.convert_to_wav_btn)
        
        self.convert_to_scd_btn = QPushButton('Convert Selected to SCD (S)')
        self.convert_to_scd_btn.clicked.connect(self.convert_selected_to_scd)
        self.convert_to_scd_btn.setEnabled(False)  # Disabled initially
        self.convert_to_scd_btn.setToolTip('Convert selected library files to SCD format')
        convert_buttons_layout.addWidget(self.convert_to_scd_btn)
        
        self.open_loop_editor_btn = QPushButton('Open Loop Editor (L)')
        self.open_loop_editor_btn.clicked.connect(self.open_loop_editor)
        self.open_loop_editor_btn.setEnabled(False)  # Disabled initially
        self.open_loop_editor_btn.setToolTip('Edit loop points for selected SCD or WAV file with professional waveform editor')
        convert_buttons_layout.addWidget(self.open_loop_editor_btn)
        
        library_layout.addLayout(convert_buttons_layout)

        # Now that both file lists exist, initialize self.library
        self.library = AudioLibrary(self.file_list, self.kh_rando_exporter, self.kh_rando_file_list, self.kh_rando_categories)
        
        # Initialize selection handling flag
        self._updating_selection = False
        if self.config.kh_rando_folder:
            self.set_kh_rando_folder(self.config.kh_rando_folder)
        
        # Initial scan to populate file list
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
        
        # Apply folder organization since it's checked by default
        if self.organize_by_folder_cb.isChecked():
            self._organize_files_by_folder()
        
        # Delay KH Rando section count update to ensure UI is ready
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._update_kh_rando_section_counts)

        library_panel.setLayout(library_layout)
        return library_panel

    def on_kh_rando_selection_changed(self):
        """Handle KH Rando selection changes"""
        if self._updating_selection:
            return
            
        # Get selected items from KH Rando list
        selected_items = []
        if hasattr(self, 'kh_rando_file_list'):
            selected_items = self.kh_rando_file_list.selectedItems()
        
        # Filter out category headers from selection
        file_items = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
                file_items.append(item)
        
        # Clear regular file list selection to avoid conflicts
        if file_items:
            self._updating_selection = True
            self.file_list.clearSelection()
            self._updating_selection = False
        
        # Update button states
        self.on_library_selection_changed_common(file_items)
    
    def setup_media_player(self):
        """Setup the media player and related components"""
        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.stateChanged.connect(self.update_state)
        self.player.mediaStatusChanged.connect(self.media_status_changed)
        self.duration = 0

        # Timer for updating time label
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_time_label)

    def setup_title_bar_theming(self):
        """Setup title bar to respect OS dark mode on Windows 11"""
        apply_title_bar_theming(self)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Delete key shortcut for deleting selected files
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.delete_selected_files)
        
        # Ctrl+L shortcut for opening file location
        open_location_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        open_location_shortcut.activated.connect(self.open_file_location)
        
        # L key shortcut for opening loop editor
        loop_editor_shortcut = QShortcut(QKeySequence("L"), self)
        loop_editor_shortcut.activated.connect(self.open_loop_editor)
        
        # E key shortcut for exporting selected to KH Rando
        export_selected_shortcut = QShortcut(QKeySequence("E"), self)
        export_selected_shortcut.activated.connect(self.export_selected_to_kh_rando)
        
        # M key shortcut for exporting missing to KH Rando
        export_missing_shortcut = QShortcut(QKeySequence("M"), self)
        export_missing_shortcut.activated.connect(self.export_missing_to_kh_rando)
        
        # F5 key shortcut for rescanning library
        rescan_shortcut = QShortcut(QKeySequence("F5"), self)
        rescan_shortcut.activated.connect(self.rescan_library)
        
        # W key shortcut for converting selected to WAV
        convert_wav_shortcut = QShortcut(QKeySequence("W"), self)
        convert_wav_shortcut.activated.connect(self.convert_selected_to_wav)
        
        # S key shortcut for converting selected to SCD
        convert_scd_shortcut = QShortcut(QKeySequence("S"), self)
        convert_scd_shortcut.activated.connect(self.convert_selected_to_scd)
        
        # Space key shortcut for play/pause
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        play_pause_shortcut.activated.connect(self.toggle_play_pause)
        
        


    # === Library Management ===
    def add_library_folder(self):
        """Add a folder to the library"""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder and folder not in self.config.library_folders:
            self.config.library_folders.append(folder)
            self.folder_list.addItem(folder)
            self.config.save_settings()
            self.rescan_library()

    def on_folder_selection_changed(self):
        """Handle folder list selection changes"""
        has_selection = self.folder_list.currentItem() is not None
        self.remove_folder_btn.setEnabled(has_selection)

    def remove_library_folder(self):
        """Remove selected folder from library"""
        current_row = self.folder_list.currentRow()
        if current_row >= 0:
            self.config.library_folders.pop(current_row)
            self.folder_list.takeItem(current_row)
            self.config.save_settings()
            self.rescan_library()

    def toggle_subdirs(self, state):
        """Toggle subdirectory scanning"""
        self.config.scan_subdirs = bool(state)
        self.config.save_settings()
        # Only rescan if self.library is initialized
        if hasattr(self, 'library') and self.library:
            self.rescan_library()
    
    def select_kh_rando_folder(self):
        """Select KH Rando music folder"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            'Select KH Rando Music Folder',
            self.config.kh_rando_folder if self.config.kh_rando_folder else ""
        )
        if folder:
            self.set_kh_rando_folder(folder)
    
    def set_kh_rando_folder(self, folder_path):
        """Set and validate KH Rando folder"""
        if self.kh_rando_exporter.is_valid_kh_rando_folder(folder_path):
            self.config.kh_rando_folder = folder_path
            self.config.save_settings()
            self.kh_rando_exporter.set_kh_rando_path(folder_path)
            
            # Update UI
            folder_name = os.path.basename(folder_path)
            self.kh_rando_path_label.setText(f"✓ {folder_name}")
            self.kh_rando_path_label.setStyleSheet("color: green;")
            
            # Enable the open folder button
            self.open_kh_rando_btn.setEnabled(True)
            
            # Do NOT add KH Rando folder to library folders - it's separate
            # KH Rando folder is for export destination only, not for scanning
            
            # Refresh library to show KH Rando status
            if hasattr(self, 'library') and self.library:
                self.rescan_library()
        else:
            show_themed_message(
                self, QMessageBox.Warning,
                "Invalid KH Rando Folder",
                "The selected folder does not appear to be a valid KH Rando music folder.\n\n" +
                "Expected subfolders (case-insensitive): atlantica, battle, boss, cutscene, field, title, wild\n\n" +
                "At least 4 of these folders must be present."
            )

    def open_kh_rando_folder(self):
        """Open the KH Rando folder in file explorer"""
        if not self.config.kh_rando_folder or not os.path.exists(self.config.kh_rando_folder):
            show_themed_message(
                self, QMessageBox.Warning,
                "No KH Rando Folder",
                "Please select a valid KH Rando folder first."
            )
            return
        
        try:
            # Open folder in Windows Explorer
            os.startfile(self.config.kh_rando_folder)
        except Exception as e:
            show_themed_message(
                self, QMessageBox.Warning,
                "Error Opening Folder",
                f"Could not open the KH Rando folder:\n{str(e)}"
            )

    def rescan_library(self):
        """Rescan library folders"""
        if not hasattr(self, 'library') or not self.library:
            return
            
        # Store current state
        current_search = ""
        if hasattr(self, 'search_input'):
            current_search = self.search_input.text()
            
        organize_by_folder = False
        if hasattr(self, 'organize_by_folder_cb'):
            organize_by_folder = self.organize_by_folder_cb.isChecked()
            
        # Clear search temporarily to get all files
        if current_search:
            self.search_input.clear()
            
        # Do the scan
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
        
        # Force update of KH Rando section counts after rescan
        self._update_kh_rando_section_counts()
        
        # Force update of KH Rando section counts after rescan
        self._update_kh_rando_section_counts()

        # Update UI
        self.folder_list.clear()
        for folder in self.config.library_folders:
            self.folder_list.addItem(folder)
        self.subdirs_checkbox.setChecked(self.config.scan_subdirs)
        
        # Apply organization if needed
        if organize_by_folder:
            self._organize_files_by_folder()
        
        # Restore search filter if it was active
        if current_search:
            self.search_input.setText(current_search)
            self.filter_library_files()
    
    def filter_library_files(self):
        """Filter library files based on search text"""
        search_text = self.search_input.text().lower()
        
        # Show all items if search is empty
        if not search_text:
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item.setHidden(False)
            return
        
        # Check if we're in folder organization mode
        is_folder_mode = self.organize_by_folder_cb.isChecked()
        
        if is_folder_mode:
            # In folder mode, we need to handle folder headers and their files
            current_folder = None
            folder_has_matches = False
            folder_header_item = None
            
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                
                if file_path and file_path.startswith("FOLDER_HEADER:"):
                    # This is a folder header
                    if folder_header_item is not None:
                        # Process previous folder
                        folder_header_item.setHidden(not folder_has_matches)
                    
                    # Start new folder
                    folder_header_item = item
                    folder_has_matches = False
                    current_folder = file_path.replace("FOLDER_HEADER:", "")
                    
                else:
                    # This is a file item
                    item_text = item.text().lower()
                    folder_path = os.path.dirname(file_path).lower() if file_path else ""
                    
                    # Show item if search text matches filename or folder
                    matches = (search_text in item_text or 
                              search_text in folder_path or
                              search_text in os.path.basename(folder_path) or
                              (current_folder and search_text in current_folder.lower()))
                    
                    item.setHidden(not matches)
                    if matches:
                        folder_has_matches = True
            
            # Process the last folder
            if folder_header_item is not None:
                folder_header_item.setHidden(not folder_has_matches)
        else:
            # Regular flat mode filtering
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                item_text = item.text().lower()
                folder_path = os.path.dirname(file_path).lower() if file_path else ""
                
                # Show item if search text matches filename or folder
                matches = (search_text in item_text or 
                          search_text in folder_path or
                          search_text in os.path.basename(folder_path))
                
                item.setHidden(not matches)
    
    def clear_search(self):
        """Clear the search input and show all files"""
        self.search_input.clear()
        self.filter_library_files()
    
    def toggle_folder_organization(self):
        """Toggle between flat and folder-organized view"""
        organize_by_folder = self.organize_by_folder_cb.isChecked()
        
        if organize_by_folder:
            self._organize_files_by_folder()
        else:
            # Clear folder states when switching to flat view
            if hasattr(self, '_folder_expanded_states'):
                self._folder_expanded_states.clear()
            # Rescan to get flat view
            self.rescan_library()
    
    def _organize_files_by_folder(self):
        """Reorganize files by their originating folder with collapsible headers"""
        if not hasattr(self, 'library') or not self.library:
            return
            
        # Store current search text to preserve filtering
        current_search = ""
        if hasattr(self, 'search_input'):
            current_search = self.search_input.text()
            
        # Temporarily clear search to get all files
        if current_search:
            self.search_input.clear()
            
        # Wait for the library to be updated without search filter
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
            
        # Collect all files with their paths
        files_by_folder = {}
        
        # Get all items from the fresh scan
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path and not file_path.startswith("FOLDER_HEADER"):
                folder = os.path.dirname(file_path)
                
                # Better folder name handling
                if folder and folder != ".":
                    folder_name = os.path.basename(folder)
                    # Handle empty folder names
                    if not folder_name:
                        folder_name = folder  # Use full path if basename is empty
                else:
                    folder_name = "Files (No Folder)"  # Better name than "Root"
                    
                if folder_name not in files_by_folder:
                    files_by_folder[folder_name] = []
                files_by_folder[folder_name].append((item.text(), file_path, item.foreground()))
        
        # Cache the files data for instant expansion
        self._files_by_folder_cache = files_by_folder
        
        # Clear and repopulate with folder organization
        self.file_list.clear()
        
        # Store folder states if they don't exist yet
        if not hasattr(self, '_folder_expanded_states'):
            self._folder_expanded_states = {}
        
        for folder_name in sorted(files_by_folder.keys()):
            # Default to expanded if not set
            if folder_name not in self._folder_expanded_states:
                self._folder_expanded_states[folder_name] = True
            
            is_expanded = self._folder_expanded_states[folder_name]
            arrow = "▼" if is_expanded else "▶"
            file_count = len(files_by_folder[folder_name])
            
            # Add collapsible folder header
            header_item = QListWidgetItem(f"{arrow} 📁 {folder_name} ({file_count})")
            header_item.setData(Qt.UserRole, f"FOLDER_HEADER:{folder_name}")
            header_item.setForeground(QColor('lightblue'))
            header_item.setFlags(header_item.flags() | Qt.ItemIsSelectable)  # Make selectable for clicking
            self.file_list.addItem(header_item)
            
            # Add files in this folder (only if expanded)
            if is_expanded:
                for file_text, file_path, file_color in sorted(files_by_folder[folder_name]):
                    file_item = QListWidgetItem(f"    {file_text}")  # Indent files
                    file_item.setData(Qt.UserRole, file_path)
                    if file_color:
                        file_item.setForeground(file_color)
                    self.file_list.addItem(file_item)
        
        # Restore search filter if it was active
        if current_search:
            self.search_input.setText(current_search)
            self.filter_library_files()

    def on_kh_rando_item_clicked(self, item):
        """Handle single clicks on KH Rando items (for category expansion and selection)"""
        file_path = item.data(Qt.UserRole)
        
        # Handle category header single clicks
        if file_path and file_path.startswith("KH_CATEGORY_HEADER:"):
            category_key = file_path.replace("KH_CATEGORY_HEADER:", "")
            self._toggle_kh_category_expansion(category_key)
            return
        
        # Clear regular file list selection to avoid conflicts
        if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
            self._updating_selection = True
            self.file_list.clearSelection()
            self._updating_selection = False

    def on_library_item_clicked(self, item):
        """Handle single clicks on library items (for folder expansion and selection)"""
        file_path = item.data(Qt.UserRole)
        
        # Handle folder header single clicks
        if file_path and file_path.startswith("FOLDER_HEADER:"):
            folder_name = file_path.replace("FOLDER_HEADER:", "")
            
            # Get click position to determine if arrow was clicked
            cursor_pos = self.file_list.mapFromGlobal(QCursor.pos())
            item_rect = self.file_list.visualItemRect(item)
            
            # Arrow is in the first ~20 pixels of the item
            if cursor_pos.x() - item_rect.x() <= 20:
                # Clicked on arrow - toggle expansion
                self._toggle_folder_expansion(folder_name)
            else:
                # Clicked on text - select all files in folder
                self._select_files_in_folder(folder_name)

    def load_from_library(self, item):
        """Load file from library double-click and auto-play"""
        file_path = item.data(Qt.UserRole)
        
        # Ignore double-clicks on folder headers - only single clicks should toggle
        if file_path and file_path.startswith("FOLDER_HEADER:"):
            return  # Do nothing on double-click
        
        # Load and play files on double-click
        if file_path and file_path != "FOLDER_HEADER":  # Skip folder headers
            self.load_file_path(file_path, auto_play=True)
    
    def _update_kh_rando_section_counts(self):
        """Force update of KH Rando list after library scan"""
        if hasattr(self, 'kh_rando_file_list'):
            self._populate_kh_rando_list()
            
            # Force Qt to process the UI updates
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

    def _select_files_in_folder(self, folder_name):
        """Select all files in the specified folder"""
        # Clear current selection
        self.file_list.clearSelection()
        
        # Find and select all files in this folder
        found_folder = False
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            
            if file_path == f"FOLDER_HEADER:{folder_name}":
                found_folder = True
                continue  # Skip the folder header itself
                
            elif found_folder and file_path and not file_path.startswith("FOLDER_HEADER"):
                # This is a file in our target folder
                item.setSelected(True)
                
            elif found_folder and file_path and file_path.startswith("FOLDER_HEADER"):
                # We've reached the next folder, stop selecting
                break

    def _toggle_kh_category_expansion(self, category_key):
        """Toggle the expansion state of a KH Rando category"""
        if category_key not in self.kh_rando_category_states:
            return
            
        # Toggle state
        current_state = self.kh_rando_category_states[category_key]
        self.kh_rando_category_states[category_key] = not current_state
        
        # Refresh the KH Rando list to reflect the change
        self._populate_kh_rando_list()

    def _populate_kh_rando_list(self):
        """Populate the KH Rando list with categories and files"""
        if not hasattr(self, 'kh_rando_file_list') or not hasattr(self, 'library'):
            return
            
        # Store current selection
        selected_paths = []
        for item in self.kh_rando_file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path and not path.startswith("KH_CATEGORY_HEADER:"):
                selected_paths.append(path)
        
        # Clear the list
        self.kh_rando_file_list.clear()
        
        # Get files by category from the library
        if hasattr(self.library, 'kh_rando_files_by_category'):
            files_by_category = self.library.kh_rando_files_by_category
        else:
            files_by_category = {}
        
        # Add each category with its files
        for category_key, category_name in self.kh_rando_categories.items():
            is_expanded = self.kh_rando_category_states.get(category_key, True)
            category_files = files_by_category.get(category_key, [])
            file_count = len(category_files)
            
            # Add category header
            arrow = "▼" if is_expanded else "▶"
            header_item = QListWidgetItem(f"{arrow} 📁 {category_name} ({file_count})")
            header_item.setData(Qt.UserRole, f"KH_CATEGORY_HEADER:{category_key}")
            header_item.setForeground(QColor('lightblue'))
            header_item.setFlags(header_item.flags() | Qt.ItemIsSelectable)
            self.kh_rando_file_list.addItem(header_item)
            
            # Add files if expanded
            if is_expanded and category_files:
                for file_info in sorted(category_files):
                    file_path, display_name = file_info
                    file_item = QListWidgetItem(f"    {display_name}")  # Indent files
                    file_item.setData(Qt.UserRole, file_path)
                    self.kh_rando_file_list.addItem(file_item)
        
        # Restore selection
        if selected_paths:
            for i in range(self.kh_rando_file_list.count()):
                item = self.kh_rando_file_list.item(i)
                if item.data(Qt.UserRole) in selected_paths:
                    item.setSelected(True)

    def _toggle_folder_expansion(self, folder_name):
        """Toggle the expansion state of a folder - optimized for instant response"""
        if not hasattr(self, '_folder_expanded_states'):
            self._folder_expanded_states = {}
            
        # Toggle state
        current_state = self._folder_expanded_states.get(folder_name, True)
        self._folder_expanded_states[folder_name] = not current_state
        new_state = not current_state
        
        # Find the folder header and update it immediately
        folder_header_item = None
        folder_header_index = -1
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path == f"FOLDER_HEADER:{folder_name}":
                folder_header_item = item
                folder_header_index = i
                break
        
        if folder_header_item is None:
            return  # Folder header not found
        
        # Update the arrow immediately
        arrow = "▼" if new_state else "▶"
        current_text = folder_header_item.text()
        # Extract the file count from the current text
        if "(" in current_text and ")" in current_text:
            file_count_part = current_text[current_text.rfind("("):]
            folder_header_item.setText(f"{arrow} 📁 {folder_name} {file_count_part}")
        
        if new_state:
            # Expanding - we need to add the files
            # Find files that belong to this folder from our stored data
            if hasattr(self, '_files_by_folder_cache') and folder_name in self._files_by_folder_cache:
                files_to_add = self._files_by_folder_cache[folder_name]
                
                # Insert files right after the header
                insert_position = folder_header_index + 1
                for file_text, file_path, file_color in sorted(files_to_add):
                    file_item = QListWidgetItem(f"    {file_text}")  # Indent files
                    file_item.setData(Qt.UserRole, file_path)
                    if file_color:
                        file_item.setForeground(file_color)
                    self.file_list.insertItem(insert_position, file_item)
                    insert_position += 1
        else:
            # Collapsing - remove all files under this folder
            items_to_remove = []
            for i in range(folder_header_index + 1, self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                
                # Stop when we hit another folder header
                if file_path and file_path.startswith("FOLDER_HEADER:"):
                    break
                    
                # This is a file under our folder
                items_to_remove.append(i)
            
            # Remove items in reverse order to maintain indices
            for i in reversed(items_to_remove):
                self.file_list.takeItem(i)

    def update_library_selection(self, file_path):
        """Update library list selection to highlight the currently playing track"""
        if not hasattr(self, 'file_list') or not self.file_list:
            return
            
        # Clear current selection first
        self.file_list.clearSelection()
        if hasattr(self, 'kh_rando_sections'):
            for section in self.kh_rando_sections.values():
                section.get_file_list().clearSelection()
        
        # Find and select the item with matching file path in regular library
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item and item.data(Qt.UserRole) == file_path:
                self.file_list.setCurrentItem(item)
                self.file_list.scrollToItem(item)
                return  # Found and selected, we're done
        
        # Check KH Rando sections
        if hasattr(self, 'kh_rando_sections'):
            for section in self.kh_rando_sections.values():
                file_list = section.get_file_list()
                for i in range(file_list.count()):
                    item = file_list.item(i)
                    if item and item.data(Qt.UserRole) == file_path:
                        file_list.setCurrentItem(item)
                        file_list.scrollToItem(item)
                        return  # Found and selected, we're done
        
        # File not found in library - add it temporarily for this session
        if hasattr(self, 'library') and self.library and os.path.exists(file_path):
            from pathlib import Path
            self.library._add_file_to_library(Path(file_path))
            
            # Now try to select it again in regular library
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item and item.data(Qt.UserRole) == file_path:
                    self.file_list.setCurrentItem(item)
                    self.file_list.scrollToItem(item)
                    break
    
    def on_library_selection_changed(self):
        """Handle library selection changes"""
        if self._updating_selection:
            return
            
        selected_items = self.file_list.selectedItems()
        
        # Clear KH Rando selections to avoid conflicts
        if selected_items and hasattr(self, 'kh_rando_file_list'):
            self._updating_selection = True
            self.kh_rando_file_list.clearSelection()
            self._updating_selection = False
        
        self.on_library_selection_changed_common(selected_items)
    
    def on_library_selection_changed_common(self, selected_items):
        """Common handler for both regular and KH Rando selection changes"""
        has_selection = len(selected_items) > 0
        single_selection = len(selected_items) == 1
        # Enable open location button if single selection OR if there's a currently playing file and no multi-selection
        can_open_location = single_selection or (len(selected_items) == 0 and self.current_file is not None)
        
        # Check file types for smart conversion button enabling
        has_non_wav_files = False
        has_non_scd_files = False
        single_supported_selection = False
        
        if has_selection:
            for item in selected_items:
                file_path = item.data(Qt.UserRole)
                if file_path:
                    ext = file_path.lower()
                    if not ext.endswith('.wav'):
                        has_non_wav_files = True
                    if not ext.endswith('.scd'):
                        has_non_scd_files = True
                    
                    # Check for loop editor support (single selection only)
                    if single_selection and (ext.endswith('.scd') or ext.endswith('.wav')):
                        single_supported_selection = True
        
        self.export_selected_btn.setEnabled(has_selection)
        self.delete_selected_btn.setEnabled(has_selection)
        # Only enable conversion if there are files that aren't already in that format
        self.convert_to_wav_btn.setEnabled(has_selection and has_non_wav_files)
        self.convert_to_scd_btn.setEnabled(has_selection and has_non_scd_files)
        self.open_file_location_btn.setEnabled(can_open_location)
        self.open_loop_editor_btn.setEnabled(single_supported_selection)
    
    def get_all_selected_items(self):
        """Get all selected items from both regular and KH Rando lists"""
        selected_items = []
        
        # Get regular library selections
        selected_items.extend(self.file_list.selectedItems())
        
        # Get KH Rando list selections (filter out headers)
        if hasattr(self, 'kh_rando_file_list'):
            for item in self.kh_rando_file_list.selectedItems():
                file_path = item.data(Qt.UserRole)
                if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
                    selected_items.append(item)
        
        return selected_items

    def delete_selected_files(self):
        """Delete selected files to recycle bin with confirmation"""
        selected_items = self.get_all_selected_items()
        if not selected_items:
            show_themed_message(self, QMessageBox.Information, "No Selection", "Please select one or more files to delete.")
            return
        
        # Get file paths
        files_to_delete = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                files_to_delete.append(file_path)
        
        if not files_to_delete:
            show_themed_message(self, QMessageBox.Warning, "No Valid Files", "No valid files found in selection.")
            return
        
        # Show confirmation (updated to mention recycle bin)
        msg = f"🗑️  Move {len(files_to_delete)} file(s) to Recycle Bin?\n\n"
        msg += "Files can be restored from the Recycle Bin if needed.\n\n"
        msg += "Files to delete:\n" + "\n".join(f"• {os.path.basename(f)}" for f in files_to_delete[:10])
        if len(files_to_delete) > 10:
            msg += f"\n• ... and {len(files_to_delete) - 10} more"
        
        reply = show_themed_message(self, QMessageBox.Question, "Move to Recycle Bin", msg,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        # Delete files to recycle bin
        deleted_count = 0
        failed_files = []
        
        for file_path in files_to_delete:
            if send_to_recycle_bin(file_path):
                deleted_count += 1
            else:
                failed_files.append(os.path.basename(file_path))
        
        # Show results
        if failed_files:
            msg = f"Moved {deleted_count} file(s) to Recycle Bin.\n\nFailed to delete {len(failed_files)} file(s):\n"
            msg += "\n".join(f"• {f}" for f in failed_files[:5])
            if len(failed_files) > 5:
                msg += f"\n• ... and {len(failed_files) - 5} more"
            show_themed_message(self, QMessageBox.Warning, "Deletion Results", msg)
        else:
            show_themed_message(self, QMessageBox.Information, "Files Moved", f"Successfully moved {deleted_count} file(s) to Recycle Bin.")
        
        # Refresh library
        if hasattr(self, 'library') and self.library:
            self.rescan_library()

    def open_file_location(self):
        """Open the folder containing the selected file or currently playing file in File Explorer"""
        selected_items = self.get_all_selected_items()
        
        # Determine which file to open location for
        file_path = None
        source_description = ""
        
        if len(selected_items) == 1:
            # Use selected file from library
            file_path = selected_items[0].data(Qt.UserRole)
            source_description = "selected file"
        elif len(selected_items) == 0 and self.current_file:
            # Use currently playing file if no selection
            file_path = self.current_file
            source_description = "currently playing file"
        elif len(selected_items) > 1:
            show_themed_message(self, QMessageBox.Information, "Multiple Selection", 
                              "Please select exactly one file to open its location, or use no selection to open the currently playing file's location.")
            return
        else:
            show_themed_message(self, QMessageBox.Information, "No File Available", 
                              "Please select a file from the library or load a file to play first.")
            return
        
        if not file_path or not os.path.exists(file_path):
            show_themed_message(self, QMessageBox.Warning, "File Not Found", 
                              f"The {source_description} no longer exists on disk.")
            return
        
        try:
            import subprocess
            import platform
            
            folder_path = os.path.dirname(file_path)
            
            if platform.system() == "Windows":
                # On Windows, use explorer to select the file - don't check return code as explorer can return non-zero even on success
                normalized_path = os.path.normpath(file_path)
                subprocess.run(f'explorer /select,"{normalized_path}"', shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path], check=True)
            else:  # Linux and others
                # Try common file managers
                subprocess.run(["xdg-open", folder_path], check=True)
                
        except Exception as e:
            show_themed_message(self, QMessageBox.Warning, "Cannot Open Location", 
                              f"Failed to open file location:\n{str(e)}")

    def convert_selected_to_wav(self):
        """Convert selected library files to WAV"""
        self.conversion_manager.convert_selected_to_wav()

    def convert_selected_to_scd(self):
        """Convert selected library files to SCD"""
        self.conversion_manager.convert_selected_to_scd()

    def open_loop_editor(self):
        """Open the loop editor for the selected SCD or WAV file"""
        selected_items = self.get_all_selected_items()
        if not selected_items or len(selected_items) != 1:
            show_themed_message(self, QMessageBox.Information, "Invalid Selection", 
                               "Please select exactly one SCD or WAV file to edit loop points.")
            return
        
        file_path = selected_items[0].data(Qt.UserRole)
        if not file_path:
            show_themed_message(self, QMessageBox.Information, "Invalid File", 
                               "Unable to get file path.")
            return
        
        ext = file_path.lower()
        if not (ext.endswith('.scd') or ext.endswith('.wav')):
            show_themed_message(self, QMessageBox.Information, "Invalid File Type", 
                               "Loop editor supports SCD and WAV files only.")
            return
        
        try:
            # Show loading dialog
            from ui.conversion_manager import SimpleStatusDialog
            
            loading_dialog = SimpleStatusDialog("Loop Editor", self)
            loading_dialog.update_status("Loading loop editor...")
            loading_dialog.show()
            
            # Load the file into the loop manager
            if ext.endswith('.wav'):
                loading_dialog.update_status("Loading WAV file...")
                # For WAV files, use them directly
                success = self.loop_manager.load_wav_file(file_path)
            else:
                loading_dialog.update_status("Converting SCD to WAV...")
                # For SCD files, use the existing conversion workflow
                success = self.loop_manager.load_file_for_editing(file_path)
            
            if not success:
                loading_dialog.close_dialog()
                show_themed_message(self, QMessageBox.Critical, "Load Error", 
                                   "Failed to load audio file for editing.")
                return
            
            loading_dialog.update_status("Initializing loop editor...")
            
            # Create and show the loop editor dialog
            loop_editor = LoopEditorDialog(self.loop_manager, self)
            loading_dialog.close_dialog()
            loop_editor.exec_()
        except Exception as e:
            if 'loading_dialog' in locals():
                loading_dialog.close_dialog()
            show_themed_message(self, QMessageBox.Critical, "Loop Editor Error", 
                               f"Failed to open loop editor:\n{str(e)}")

    # === File Loading ===
    def load_file(self):
        """Load audio file via file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Audio File', '', 
            'Audio Files (*.scd *.wav *.mp3 *.ogg *.flac);;SCD Files (*.scd);;WAV Files (*.wav);;MP3 Files (*.mp3);;OGG Files (*.ogg);;FLAC Files (*.flac);;All Files (*.*)'
        )
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path, auto_play=False):
        """Load audio file from path"""
        self.auto_play_after_load = auto_play
        
        # Update metadata display to show loading
        self.metadata_label.setText("Loading audio file...")
        
        # Start file loading in thread
        self.file_load_thread = FileLoadThread(file_path)
        self.file_load_thread.finished.connect(self.on_file_loaded)
        self.file_load_thread.error.connect(self.on_file_load_error)
        self.file_load_thread.start()
        
    def on_file_loaded(self, file_path):
        """Handle file loaded signal"""
        self.converter.cleanup_temp_files()
        self.current_file = file_path
        
        # Update library selection to highlight current track
        self.update_library_selection(file_path)
        
        # Update button states now that we have a current file
        self.on_library_selection_changed()
        
        file_ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        self.label.setText(filename)
        self.setWindowTitle(f'SCDPlayer v{__version__} - {filename}')
        
        # Extract and display metadata
        self.display_file_metadata(file_path)
        
        # Update playlist
        self.playlist = self.library.get_playlist()
        self.current_playlist_index = self.library.find_file_index(file_path)
        
        # Handle different file types
        if file_ext == '.scd':
            wav_file = self.converter.convert_scd_to_wav(file_path)
            if wav_file:
                self.enable_playback_controls()
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText('Failed to convert SCD file.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
                
        elif file_ext == '.wav':
            self.enable_playback_controls()
            media_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.player.setMedia(QMediaContent(media_url))
            
        else:  # MP3, OGG, FLAC
            wav_file = self.converter.convert_to_wav_temp(file_path)
            if wav_file:
                self.enable_playback_controls()
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText(f'Failed to convert {file_ext.upper()} file for playback.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
        
        # Auto-play if requested
        if hasattr(self, 'auto_play_after_load') and self.auto_play_after_load:
            self.auto_play_after_load = False
            QTimer.singleShot(100, self.play_audio)
        
        # Update library selection to highlight the loaded file (enables export/convert buttons)
        self.update_library_selection(file_path)
        
    def on_file_load_error(self, error_msg):
        """Handle file load error"""
        self.label.setText(f'Error loading file: {error_msg}')
        self.metadata_label.setText(f'Error: {error_msg}')

    def enable_playback_controls(self):
        """Enable all playback control buttons"""
        self.play_pause_btn.setEnabled(True)
        self.play_pause_btn.setIcon(create_icon("play"))
        self.play_pause_btn.setText("")  # Ensure no text
        self.play_pause_btn.setToolTip("Play")
        self.prev_btn.setEnabled(len(self.playlist) > 1)
        self.next_btn.setEnabled(len(self.playlist) > 1)

    # === Playback Controls ===
    def toggle_play_pause(self):
        """Toggle between play and pause states"""
        if self.player.state() == QMediaPlayer.PlayingState:
            self.pause_audio()
        else:
            self.play_audio()

    def play_audio(self):
        if self.current_file:
            self.player.play()
            self.timer.start()

    def pause_audio(self):
        self.player.pause()
        self.timer.stop()

    def stop_audio(self):
        self.player.stop()
        self.timer.stop()

    def previous_track(self):
        """Play previous track in playlist"""
        if len(self.playlist) > 1 and self.current_playlist_index > 0:
            self.current_playlist_index -= 1
            self.load_file_path(self.playlist[self.current_playlist_index], auto_play=True)

    def next_track(self):
        """Play next track in playlist"""
        if len(self.playlist) > 1 and self.current_playlist_index < len(self.playlist) - 1:
            self.current_playlist_index += 1
            self.load_file_path(self.playlist[self.current_playlist_index], auto_play=True)

    def on_scrub_start(self):
        """Called when user starts dragging the slider"""
        self.is_scrubbing = True
        self.is_playing_before_scrub = (self.player.state() == QMediaPlayer.PlayingState)
        if self.is_playing_before_scrub:
            # Directly pause the player without updating UI
            self.player.pause()

    def on_scrub_end(self):
        """Called when user releases the slider"""
        # Resume playing if it was playing before scrubbing
        if self.is_playing_before_scrub:
            # Directly resume the player without updating UI
            self.player.play()
        self.is_scrubbing = False  # Set this AFTER resuming to allow final icon update

    def seek_position(self, position):
        """Seek to position - only actually seek when not scrubbing rapidly"""
        self.player.setPosition(position)

    def update_position(self, position):
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(position)
        self.seek_slider.blockSignals(False)
        self.update_time_label()

    def update_duration(self, duration):
        self.duration = duration
        self.seek_slider.setRange(0, duration)
        self.update_time_label()

    def update_time_label(self):
        pos = self.player.position() // 1000
        dur = self.duration // 1000 if self.duration else 0
        self.time_label.setText(f'{format_time(pos)} / {format_time(dur)}')

    def update_state(self, state):
        # Don't update UI during scrubbing
        if getattr(self, 'is_scrubbing', False):
            return
            
        if state == QMediaPlayer.StoppedState:
            self.timer.stop()
            # Update icon to play state when stopped
            self.play_pause_btn.setIcon(create_icon("play"))
            self.play_pause_btn.setText("")  # Ensure no text
            self.play_pause_btn.setToolTip("Play")
        elif state == QMediaPlayer.PlayingState:
            # Update to pause icon when playing
            self.play_pause_btn.setIcon(create_icon("pause"))
            self.play_pause_btn.setText("")  # Ensure no text
            self.play_pause_btn.setToolTip("Pause")
        elif state == QMediaPlayer.PausedState:
            # Update to play icon when paused
            self.play_pause_btn.setIcon(create_icon("play"))
            self.play_pause_btn.setText("")  # Ensure no text
            self.play_pause_btn.setToolTip("Play")

    def media_status_changed(self, status):
        """Handle media status changes for auto-advance"""
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            if len(self.playlist) > 1 and self.current_playlist_index < len(self.playlist) - 1:
                self.next_track()

    def display_file_metadata(self, file_path):
        """Extract and display file metadata"""
        try:
            import datetime
            
            # Get basic file info
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            file_modified = datetime.datetime.fromtimestamp(file_stat.st_mtime)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Format file size
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            
            metadata_text = f"""File: {os.path.basename(file_path)}
Size: {size_str}
Type: {file_ext.upper()} Audio File
Modified: {file_modified.strftime('%Y-%m-%d %H:%M:%S')}
Path: {file_path}"""

            # Try to get audio-specific metadata for non-SCD files
            if file_ext in ['.mp3', '.ogg', '.flac', '.wav']:
                try:
                    import mutagen
                    audio_file = mutagen.File(file_path)
                    if audio_file is not None:
                        # Get duration
                        if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                            duration = audio_file.info.length
                            minutes = int(duration // 60)
                            seconds = int(duration % 60)
                            metadata_text += f"\nDuration: {minutes:02d}:{seconds:02d}"
                        
                        # Get sample rate and bitrate if available
                        if hasattr(audio_file, 'info'):
                            if hasattr(audio_file.info, 'sample_rate'):
                                metadata_text += f"\nSample Rate: {audio_file.info.sample_rate} Hz"
                            if hasattr(audio_file.info, 'bitrate'):
                                metadata_text += f"\nBitrate: {audio_file.info.bitrate} kbps"
                                
                        # Get title, artist, album if available
                        tags = []
                        if 'TITLE' in audio_file or 'TIT2' in audio_file:
                            title = str(audio_file.get('TITLE', audio_file.get('TIT2', [''])[0]))
                            if title:
                                tags.append(f"Title: {title}")
                        if 'ARTIST' in audio_file or 'TPE1' in audio_file:
                            artist = str(audio_file.get('ARTIST', audio_file.get('TPE1', [''])[0]))
                            if artist:
                                tags.append(f"Artist: {artist}")
                        if 'ALBUM' in audio_file or 'TALB' in audio_file:
                            album = str(audio_file.get('ALBUM', audio_file.get('TALB', [''])[0]))
                            if album:
                                tags.append(f"Album: {album}")
                        
                        if tags:
                            metadata_text += "\n" + "\n".join(tags)
                                
                except ImportError:
                    # mutagen not available, skip audio metadata
                    pass
                except Exception as e:
                    # Error reading audio metadata, continue with basic info
                    pass
            
            elif file_ext == '.scd':
                metadata_text += "\nFormat: Square Enix SCD Audio"
                try:
                    # Try to get some basic info about the SCD file
                    with open(file_path, 'rb') as f:
                        # Read first few bytes to check for SCD signature
                        header = f.read(16)
                        if header.startswith(b'SEDBSSCF'):
                            metadata_text += "\nSCD Header: Valid (Original SCD)"
                        elif header.startswith(b'RIFF'):
                            # This is likely a WAV file with SCD extension (converted)
                            metadata_text += "\nSCD Header: WAV-based (Converted from WAV)"
                        else:
                            metadata_text += "\nSCD Header: Unknown format"
                except:
                    pass
            
            self.metadata_label.setText(metadata_text)
            
        except Exception as e:
            self.metadata_label.setText(f"Could not load metadata: {str(e)}")

    # === Conversion wrapper methods ===
    def convert_current_to_wav(self):
        """Wrapper method for conversion manager"""
        self.conversion_manager.convert_current_to_wav()
    
    def convert_current_to_scd(self):
        """Wrapper method for conversion manager"""
        self.conversion_manager.convert_current_to_scd()
    
    # === KH Rando wrapper methods ===
    def export_selected_to_kh_rando(self):
        """Wrapper method for KH Rando manager"""
        self.kh_rando_manager.export_selected_to_kh_rando()
    
    def export_missing_to_kh_rando(self):
        """Wrapper method for KH Rando manager"""
        self.kh_rando_manager.export_missing_to_kh_rando()
    
    def closeEvent(self, event):
        """Handle application close"""
        # Clean up thread
        if self.file_load_thread and self.file_load_thread.isRunning():
            self.file_load_thread.quit()
            self.file_load_thread.wait()
            
        # Clean up temp files
        self.converter.cleanup_temp_files()
        event.accept()
