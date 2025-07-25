"""Streamlined main application window for SCDPlayer"""
import os
import tempfile
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, 
    QLabel, QSlider, QSizePolicy, QListWidget, QCheckBox, QMessageBox, 
    QSplitter, QGroupBox, QProgressBar, QComboBox, QDialog, QShortcut,
    QMenuBar, QAction
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QKeySequence

from version import __version__
from ui.widgets import ScrollingLabel, create_icon, create_app_icon
from ui.styles import DARK_THEME
from ui.dialogs import show_themed_message, show_themed_file_dialog, apply_title_bar_theming
from ui.conversion_manager import ConversionManager
from ui.kh_rando_manager import KHRandoManager
from ui.help_dialog import HelpDialog
from core.converter import AudioConverter
from core.threading import FileLoadThread
from core.library import AudioLibrary
from core.kh_rando import KHRandoExporter
from utils.config import Config
from utils.helpers import format_time
from utils.updater import AutoUpdater


class SCDPlayer(QMainWindow):
    """Main SCDPlayer application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDPlayer v{__version__}')
        self.setGeometry(100, 100, 1200, 700)
        
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

        # Conversion controls
        convert_layout = QVBoxLayout()
        
        # First row: WAV/SCD conversion
        convert_row1 = QHBoxLayout()
        self.convert_to_wav_btn = QPushButton('Convert to WAV')
        self.convert_to_wav_btn.clicked.connect(self.convert_current_to_wav)
        self.convert_to_wav_btn.setEnabled(False)
        convert_row1.addWidget(self.convert_to_wav_btn)
        
        self.convert_to_scd_btn = QPushButton('Convert to SCD')
        self.convert_to_scd_btn.clicked.connect(self.convert_current_to_scd)
        self.convert_to_scd_btn.setEnabled(False)
        convert_row1.addWidget(self.convert_to_scd_btn)
        convert_layout.addLayout(convert_row1)
        
        player_layout.addLayout(convert_layout)

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
        
        header_layout.addLayout(kh_rando_layout)

        library_header.setLayout(header_layout)
        library_layout.addWidget(library_header)

        # File library
        library_layout.addWidget(QLabel('Audio Files (SCD, WAV, MP3, OGG, FLAC):'))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)  # Allow multiple selection
        self.file_list.itemDoubleClicked.connect(self.load_from_library)
        self.file_list.itemSelectionChanged.connect(self.on_library_selection_changed)
        library_layout.addWidget(self.file_list)

        # Library management buttons
        library_buttons_layout = QHBoxLayout()
        
        self.export_selected_btn = QPushButton('Export Selected to KH Rando')
        self.export_selected_btn.clicked.connect(self.export_selected_to_kh_rando)
        self.export_selected_btn.setEnabled(False)
        self.export_selected_btn.setToolTip('Export selected library files to Kingdom Hearts Randomizer music folder')
        library_buttons_layout.addWidget(self.export_selected_btn)
        
        self.export_missing_btn = QPushButton('Export Missing to KH Rando')
        self.export_missing_btn.clicked.connect(self.export_missing_to_kh_rando)
        self.export_missing_btn.setToolTip('Export library files that are not in KH Rando folder')
        library_buttons_layout.addWidget(self.export_missing_btn)
        
        self.delete_selected_btn = QPushButton('Delete Selected')
        self.delete_selected_btn.clicked.connect(self.delete_selected_files)
        self.delete_selected_btn.setToolTip('Delete selected files from disk (DEL key shortcut)')
        library_buttons_layout.addWidget(self.delete_selected_btn)
        
        library_layout.addLayout(library_buttons_layout)

        # Now that self.file_list exists, initialize self.library
        self.library = AudioLibrary(self.file_list, self.kh_rando_exporter)
        
        # Initialize KH Rando folder if saved in config
        if self.config.kh_rando_folder:
            self.set_kh_rando_folder(self.config.kh_rando_folder)
        
        # Initial scan to populate file list
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)

        library_panel.setLayout(library_layout)
        return library_panel
    
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
                "Expected subfolders: atlantica, battle, boss, cutscene, field, title, wild"
            )

    def rescan_library(self):
        """Rescan library folders"""
        if not hasattr(self, 'library') or not self.library:
            return
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)

        # Update UI
        self.folder_list.clear()
        for folder in self.config.library_folders:
            self.folder_list.addItem(folder)
        self.subdirs_checkbox.setChecked(self.config.scan_subdirs)

    def load_from_library(self, item):
        """Load file from library double-click and auto-play"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.load_file_path(file_path, auto_play=True)

    def update_library_selection(self, file_path):
        """Update library list selection to highlight the currently playing track"""
        if not hasattr(self, 'file_list') or not self.file_list:
            return
            
        # Find and select the item with matching file path
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item and item.data(Qt.UserRole) == file_path:
                self.file_list.setCurrentItem(item)
                self.file_list.scrollToItem(item)
                break
    
    def on_library_selection_changed(self):
        """Handle library selection changes"""
        selected_items = self.file_list.selectedItems()
        self.export_selected_btn.setEnabled(len(selected_items) > 0)

    def delete_selected_files(self):
        """Delete selected files from disk with confirmation"""
        selected_items = self.file_list.selectedItems()
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
        
        # Show warning confirmation
        msg = f"⚠️  PERMANENTLY DELETE {len(files_to_delete)} file(s) from disk?\n\n"
        msg += "This action CANNOT be undone!\n\n"
        msg += "Files to delete:\n" + "\n".join(f"• {os.path.basename(f)}" for f in files_to_delete[:10])
        if len(files_to_delete) > 10:
            msg += f"\n• ... and {len(files_to_delete) - 10} more"
        
        reply = show_themed_message(self, QMessageBox.Question, "Delete Files", msg,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        # Delete files
        deleted_count = 0
        failed_files = []
        
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                deleted_count += 1
            except Exception as e:
                failed_files.append(os.path.basename(file_path))
        
        # Show results
        if failed_files:
            msg = f"Deleted {deleted_count} file(s).\n\nFailed to delete {len(failed_files)} file(s):\n"
            msg += "\n".join(f"• {f}" for f in failed_files[:5])
            if len(failed_files) > 5:
                msg += f"\n• ... and {len(failed_files) - 5} more"
            show_themed_message(self, QMessageBox.Warning, "Deletion Results", msg)
        else:
            show_themed_message(self, QMessageBox.Information, "Files Deleted", f"Successfully deleted {deleted_count} file(s).")
        
        # Refresh library
        if hasattr(self, 'library') and self.library:
            self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)

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
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(False)
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText('Failed to convert SCD file.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
                
        elif file_ext == '.wav':
            self.enable_playback_controls()
            self.convert_to_wav_btn.setEnabled(False)
            self.convert_to_scd_btn.setEnabled(True)
            media_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.player.setMedia(QMediaContent(media_url))
            
        else:  # MP3, OGG, FLAC
            wav_file = self.converter.convert_to_wav_temp(file_path)
            if wav_file:
                self.enable_playback_controls()
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(True)
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText(f'Failed to convert {file_ext.upper()} file for playback.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
        
        # Auto-play if requested
        if hasattr(self, 'auto_play_after_load') and self.auto_play_after_load:
            self.auto_play_after_load = False
            QTimer.singleShot(100, self.play_audio)
        
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
