"""Streamlined main application window for SCDToolkit"""
import os
import logging
import tempfile
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, 
    QLabel, QSlider, QSizePolicy, QListWidget, QCheckBox, QMessageBox, 
    QSplitter, QGroupBox, QProgressBar, QComboBox, QDialog, QShortcut,
    QMenuBar, QAction, QApplication, QScrollArea, QFrame, QListWidgetItem,
    QLineEdit, QMenu
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QKeySequence, QCursor

from version import __version__
from ui.widgets import ScrollingLabel, create_icon, create_app_icon, LoopSlider
from ui.styles import DARK_THEME
from ui.dialogs import show_themed_message, show_themed_file_dialog, apply_title_bar_theming
from ui.conversion_manager import ConversionManager
from ui.kh_rando_manager import KHRandoManager
from ui.main_window.library_controller import LibraryController
from ui.main_window.startup import StartupController
from ui.main_window.visualizer_host import VisualizerHost
# Lazy imports for faster startup:
# from ui.help_dialog import HelpDialog  # Imported when needed
# from ui.loop_editor_dialog import LoopEditorDialog  # Imported when needed
from ui.scan_overlay import ScanOverlay
from core.loop_manager import HybridLoopManager
from core.converter import AudioConverter
from core.threading import FileLoadThread
from core.library import AudioLibrary
from core.kh_rando import KHRandoExporter
from utils.config import Config
from utils.helpers import format_time, send_to_recycle_bin
# from utils.updater import AutoUpdater  # Lazy loaded after UI is shown


class SCDToolkit(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDToolkit v{__version__}')
        self.setGeometry(100, 100, 1400, 850)

        # Core configuration and helpers
        self.config = Config()
        self.config.load_settings()
        self.kh_rando_exporter = KHRandoExporter(self)

        # Controllers
        self.library_controller = LibraryController(self)
        self.startup_controller = StartupController(self)
        self.visualizer_host = VisualizerHost(self)

        # Deferred/late-initialized components
        self.converter = None
        self.file_watcher = None

        self.current_file = None
        self.current_playlist_index = -1
        self.playlist = []
        self._loop_marker_retry_count = 0

        # UI
        self.setup_menu_bar()
        self.setup_ui()
        self.setup_media_player()

        # Overlays and chrome
        self.scan_overlay = ScanOverlay(self.centralWidget())
        self.setWindowIcon(create_app_icon())
        self.setup_title_bar_theming()
        self.setStyleSheet(DARK_THEME)

        # Threads/state
        self.file_load_thread = None

        # Begin staged startup
        self._begin_startup_initialization()

    def get_full_library_playlist(self):
        """Return a list of all file paths in the library, in folder order, regardless of UI expansion."""
        playlist = []
        files_by_folder = getattr(self.library_controller, '_files_by_folder_cache', None)
        if files_by_folder:
            for folder_name in sorted(files_by_folder.keys()):
                sorted_files = sorted(files_by_folder[folder_name], key=lambda x: os.path.basename(x[1]).lower())
                for _, file_path, _ in sorted_files:
                    if file_path and file_path not in playlist:
                        playlist.append(file_path)
        else:
            file_list = getattr(self.library_controller, 'file_list', None)
            if file_list:
                for i in range(file_list.count()):
                    item = file_list.item(i)
                    file_path = item.data(Qt.UserRole)
                    if file_path and not file_path.startswith("FOLDER_HEADER") and file_path not in playlist:
                        playlist.append(file_path)
        return playlist

    def _begin_startup_initialization(self):
        """Kick off staged initialization using the startup controller."""
        if hasattr(self, 'startup_controller'):
            self.startup_controller.begin()

    def _init_converter(self):
        self.converter = AudioConverter()
        if hasattr(self, 'kh_rando_exporter'):
            self.kh_rando_exporter.set_converter(self.converter)

    def _init_file_watcher(self):
        from core.file_watcher import LibraryFileWatcher
        self.file_watcher = LibraryFileWatcher(self)
        self.file_watcher.file_added.connect(self.library_controller._on_file_added)
        self.file_watcher.file_removed.connect(self.library_controller._on_file_removed)
        self.file_watcher.file_modified.connect(self.library_controller._on_file_modified)
        self.file_watcher.directory_added.connect(self.library_controller._on_directory_added)
        self.file_watcher.directory_removed.connect(self.library_controller._on_directory_removed)
        QTimer.singleShot(0, self._start_file_watcher)

    def _init_managers(self):
        self.conversion_manager = ConversionManager(self)
        self.kh_rando_manager = KHRandoManager(self)
        self.loop_manager = HybridLoopManager()

    def _init_shortcuts(self):
        self.setup_shortcuts()

    def _init_audio_analyzer_deferred(self):
        QTimer.singleShot(10, self._initialize_audio_analyzer)

    def _init_updater_deferred(self):
        QTimer.singleShot(100, self._initialize_auto_updater)
    
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

        # Log menu
        log_menu = menubar.addMenu('&Log')
        
        view_log_action = QAction('View Log File', self)
        view_log_action.triggered.connect(self.show_log_viewer)
        log_menu.addAction(view_log_action)
        
        log_menu.addSeparator()
        
        open_log_file_action = QAction('Open Log File', self)
        open_log_file_action.triggered.connect(self.open_log_file)
        log_menu.addAction(open_log_file_action)
        
        # Ko-fi and Discord direct buttons (last items)
        kofi_action = menubar.addAction('Support on &Ko-fi ☕')
        kofi_action.triggered.connect(self.open_kofi)
        discord_action = menubar.addAction('Join Discord')
        discord_action.triggered.connect(self.open_discord)

        
    def show_help_dialog(self):
        """Show the help dialog"""
        from ui.help_dialog import HelpDialog
        help_dialog = HelpDialog(self)
        help_dialog.exec_()
        
    def _initialize_audio_analyzer(self):
        """Initialize audio analyzer for visualizer after UI is shown"""
        from core.audio_analyzer import AudioAnalyzer
        self.audio_analyzer = AudioAnalyzer()
        
        # Connect visualizer to audio data if it exists
        host_visualizer = getattr(self.visualizer_host, 'visualizer', None)
        if host_visualizer:
            host_visualizer.set_audio_callback(self.get_visualizer_audio_data)
    
    def _initialize_auto_updater(self):
        """Initialize the auto updater after UI is shown"""
        from utils.updater import AutoUpdater
        self.auto_updater = AutoUpdater(self)
        # Check for updates after initializing (reduced delay)
        QTimer.singleShot(100, self.check_for_updates_startup)
    
    def check_for_updates_startup(self):
        """Check for updates silently on startup"""
        if hasattr(self, 'auto_updater'):
            self.auto_updater.check_for_updates(silent=True)
    
    def check_for_updates_manual(self):
        """Manually check for updates (show result)"""
        if hasattr(self, 'auto_updater'):
            self.auto_updater.check_for_updates(silent=False)
    
    def open_discord(self):
        """Open Discord server invite link"""
        import webbrowser
        webbrowser.open('https://discord.gg/FqePtT2BBM')
    
    def open_kofi(self):
        """Open Ko-fi support page"""
        import webbrowser
        webbrowser.open('https://ko-fi.com/skylect')
    
    def show_log_viewer(self):
        """Show the log viewer dialog"""
        from ui.dialogs import LogViewerDialog
        
        # Reuse existing log viewer or create new one
        if not hasattr(self, 'log_viewer') or not self.log_viewer.dialog.isVisible():
            self.log_viewer = LogViewerDialog(self)
            self.log_viewer.show()
        else:
            # Bring existing window to front
            self.log_viewer.dialog.raise_()
            self.log_viewer.dialog.activateWindow()
    
    def open_log_file(self):
        """Open the log file in default text editor"""
        import os
        import subprocess
        log_path = os.path.abspath('scdtoolkit_debug.log')
        
        # Check if file exists
        if os.path.exists(log_path):
            # Open with default application
            os.startfile(log_path)
    
    def show_musiclist_editor(self):
        """Show the musiclist.json editor"""
        from ui.musiclist_editor import MusicListEditor
        editor = MusicListEditor(self)
        editor.exec_()
    
    def open_music_pack_creator(self):
        """Open the Music Pack Creator dialog"""
        from PyQt5.QtCore import Qt, QTimer
        from ui.music_pack_creator_dialog import MusicPackCreatorDialog
        
        # Get all library files (both regular and KH Rando)
        library_files = self.get_full_library_playlist()
        
        if not library_files:
            show_themed_message(self, QMessageBox.Information, 'No Library Files',
                              'Please add some music files to your library first.')
            return
        
        # Show loading cursor
        self.setCursor(Qt.WaitCursor)
        
        # Use QTimer to update UI before creating dialog
        def create_dialog():
            try:
                # Open the dialog (non-modal so main window can be used)
                dialog = MusicPackCreatorDialog(self, library_files)
                dialog.show()
            finally:
                # Restore cursor
                self.setCursor(Qt.ArrowCursor)
        
        # Defer dialog creation to next event loop iteration
        QTimer.singleShot(10, create_dialog)
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create main widget and splitter
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        
        # Create splitter for player and library
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Player controls
        self.player_panel = self.create_player_panel()
        splitter.addWidget(self.player_panel)
        
        # Right panel - Library
        library_panel = self.library_controller.create_library_panel()
        splitter.addWidget(library_panel)
        
        # Set splitter sizes
        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        
        # Defer visualizer creation for faster startup
        QTimer.singleShot(20, self.visualizer_host.create)
    
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
        
        # Seek bar with loop markers
        self.seek_slider = LoopSlider(Qt.Horizontal)
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
        # Loop toggle button
        self.loop_btn = self.create_control_button("loop", "Loop Off", self.toggle_loop)
        self.loop_btn.setFixedSize(40, 40)
        self.loop_btn.setEnabled(True)  # Loop button should always be enabled
        self.loop_enabled = False  # Track loop state
        
        for btn in [self.prev_btn, self.play_pause_btn, self.next_btn, self.loop_btn]:
            controls_layout.addWidget(btn)
        
        # Add volume control inline with playback controls
        from ui.volume_control import VolumeControl
        self.volume_control = VolumeControl()
        self.volume_control.setVolume(getattr(self.config, 'volume', 70))
        self.volume_control.volumeChanged.connect(self.on_volume_changed)
        controls_layout.addSpacing(10)
        controls_layout.addWidget(self.volume_control)
        
        # Add the controls container to the player layout
        player_layout.addWidget(controls_container, alignment=Qt.AlignCenter)

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
        
        # High-frequency timer for accurate loop checking (every 1ms for maximum precision)
        self.loop_timer = QTimer(self)
        self.loop_timer.setInterval(1)  # 1ms = maximum precision possible
        self.loop_timer.timeout.connect(self.check_loop_position)
        self.loop_timer.start()  # Always running when player exists
        # Apply stored volume to player
        try:
            initial_vol = getattr(self.config, 'volume', 70)
            if hasattr(self, 'volume_slider'):
                self.volume_slider.setValue(int(initial_vol))
            self.player.setVolume(int(initial_vol))
        except Exception:
            pass

    def setup_title_bar_theming(self):
        """Setup title bar to respect OS dark mode on Windows 11"""
        apply_title_bar_theming(self)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Delete key shortcut for deleting selected files
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self.library_controller.delete_selected_files)
        
        # Ctrl+L shortcut for opening file location
        open_location_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        open_location_shortcut.activated.connect(self.library_controller.open_file_location)
        
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
        rescan_shortcut.activated.connect(self.library_controller.rescan_library)
        
        # W key shortcut for converting selected to WAV
        convert_wav_shortcut = QShortcut(QKeySequence("W"), self)
        convert_wav_shortcut.activated.connect(self.library_controller.convert_selected_to_wav)
        
        # S key shortcut for converting selected to SCD
        convert_scd_shortcut = QShortcut(QKeySequence("S"), self)
        convert_scd_shortcut.activated.connect(self.library_controller.convert_selected_to_scd)
        
        # Space key shortcut for play/pause
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        play_pause_shortcut.activated.connect(self.toggle_play_pause)
        
        # J key shortcut for opening music list editor
        musiclist_editor_shortcut = QShortcut(QKeySequence("J"), self)
        musiclist_editor_shortcut.activated.connect(self.show_musiclist_editor)
        
    def on_volume_changed(self, value: int):
        """Handle volume control changes and persist setting."""
        if hasattr(self, 'player') and self.player:
            try:
                self.player.setVolume(int(value))
            except Exception:
                pass
        if hasattr(self, 'config'):
            self.config.volume = int(value)
            try:
                self.config.save_settings()
            except Exception:
                logging.warning("Failed to persist volume setting")


    # === Library Management ===
    def add_library_folder(self):
        """Add a folder to the library"""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder and folder not in self.config.library_folders:
            self.config.library_folders.append(folder)
            self.folder_list.addItem(folder)
            self.config.save_settings()
            
            # Add folder to file watcher
            if hasattr(self, 'file_watcher'):
                self.file_watcher.scan_initial_files([folder], self.config.scan_subdirs)
                self.file_watcher.add_watch_paths([folder], self.config.scan_subdirs)
            
            self.rescan_library()

    def on_folder_selection_changed(self):
        """Handle folder list selection changes"""
        has_selection = self.folder_list.currentItem() is not None
        self.remove_folder_btn.setEnabled(has_selection)

    def remove_library_folder(self):
        """Remove selected folder from library"""
        current_row = self.folder_list.currentRow()
        if current_row >= 0:
            removed_folder = self.config.library_folders[current_row]
            self.config.library_folders.pop(current_row)
            self.folder_list.takeItem(current_row)
            self.config.save_settings()
            
            # Remove folder from file watcher
            if hasattr(self, 'file_watcher'):
                self.file_watcher.remove_watch_paths([removed_folder])
            
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
            
            # Update categories from detected folders
            self._update_kh_rando_categories()
            
            # Check for musiclist.json (it's in the parent directory of the music folder)
            parent_dir = os.path.dirname(folder_path)
            musiclist_path = os.path.join(parent_dir, "musiclist.json")
            has_musiclist = os.path.exists(musiclist_path)
            
            # Update UI with folder name and indicators
            folder_name = os.path.basename(folder_path)
            status_text = f"✓ {folder_name}"
            if has_musiclist:
                status_text += "  ✓ musiclist.json"
            else:
                status_text += "  ⚠ musiclist.json missing"
            self.kh_rando_path_label.setText(status_text)
            
            # Folder is always green if valid, musiclist status is separate
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
        
        # Show scanning overlay if it exists (may not exist during initial setup)
        if hasattr(self, 'scan_overlay'):
            self.scan_overlay.show_scanning("Scanning library folders...")
        
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
        
        # Set up progress callback only if overlay exists
        if hasattr(self, 'scan_overlay'):
            def on_scan_progress(current, total, filename):
                self.scan_overlay.update_progress(current, total, filename)
                # Process events to keep UI responsive
                QApplication.processEvents()
            
            self.library.set_progress_callback(on_scan_progress)
        
        try:
            # Do the scan
            self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
            
            # Repopulate KH Rando list and update section counts after rescan
            self._populate_kh_rando_list()
            self._update_kh_rando_section_counts()
            
            # Update UI
            self.folder_list.clear()
            for folder in self.config.library_folders:
                self.folder_list.addItem(folder)
            self.subdirs_checkbox.setChecked(self.config.scan_subdirs)
            
            # Apply organization if needed
            if organize_by_folder:
                # Invalidate cache since we rescanned
                if hasattr(self, '_files_by_folder_cache'):
                    del self._files_by_folder_cache
                self._organize_files_by_folder()
            
            # Restore search filter if it was active
            if current_search:
                self.search_input.setText(current_search)
                self.filter_library_files()
        
        finally:
            # Clear progress callback
            self.library.set_progress_callback(None)
            
            # Hide scanning overlay if it exists
            if hasattr(self, 'scan_overlay'):
                self.scan_overlay.hide_scanning()
    
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
            # Build cache from current flat list, then organize
            if hasattr(self, '_files_by_folder_cache'):
                del self._files_by_folder_cache
            self._organize_files_by_folder()
        else:
            # Clear folder states when switching to flat view
            if hasattr(self, '_folder_expanded_states'):
                self._folder_expanded_states.clear()
            # Rescan to get flat view
            self.rescan_library()
    
    def _get_expanded_folder_items(self):
        """Get list of currently expanded folder names"""
        if not hasattr(self, '_folder_expanded_states'):
            return []
        return [folder for folder, expanded in self._folder_expanded_states.items() if expanded]
    
    def _restore_expanded_folder_items(self, expanded_folders):
        """Restore expansion state for specified folders"""
        if not hasattr(self, '_folder_expanded_states'):
            self._folder_expanded_states = {}
        # Update states to match the provided list
        for folder in self._folder_expanded_states.keys():
            self._folder_expanded_states[folder] = folder in expanded_folders
    
    def _add_file_to_folder_cache(self, file_path: str, display_text: str, color):
        return self.library_controller._add_file_to_folder_cache(file_path, display_text, color)
    
    def _remove_file_from_folder_cache(self, file_path: str):
        return self.library_controller._remove_file_from_folder_cache(file_path)
    
    def _organize_files_by_folder(self):
        return self.library_controller._organize_files_by_folder()

    def on_kh_rando_item_clicked(self, item):
        return self.library_controller.on_kh_rando_item_clicked(item)

    def on_library_item_clicked(self, item):
        return self.library_controller.on_library_item_clicked(item)

    def load_from_library(self, item):
        return self.library_controller.load_from_library(item)
    
    def _update_kh_rando_categories(self):
        return self.library_controller._update_kh_rando_categories()
    
    def _update_kh_rando_section_counts(self):
        return self.library_controller._update_kh_rando_section_counts()
    
    def _refresh_duplicate_status(self):
        return self.library_controller._refresh_duplicate_status()

    def _select_files_in_folder(self, folder_name):
        return self.library_controller._select_files_in_folder(folder_name)

    def _toggle_kh_category_expansion(self, category_key):
        return self.library_controller._toggle_kh_category_expansion(category_key)

    def add_kh_rando_folder(self):
        return self.library_controller.add_kh_rando_folder()

    def _populate_kh_rando_list(self):
        return self.library_controller._populate_kh_rando_list()

    def _toggle_folder_expansion(self, folder_name):
        return self.library_controller._toggle_folder_expansion(folder_name)

    def update_library_selection(self, file_path):
        return self.library_controller.update_library_selection(file_path)
    
    def on_library_selection_changed(self):
        return self.library_controller.on_library_selection_changed()
    
    def on_library_selection_changed_common(self, selected_items):
        return self.library_controller.on_library_selection_changed_common(selected_items)
    
    def get_all_selected_items(self):
        return self.library_controller.get_all_selected_items()

    def delete_selected_files(self):
        return self.library_controller.delete_selected_files()

    def open_file_location(self):
        """Open the folder containing the selected file or currently playing file in File Explorer"""
        return self.library_controller.open_file_location()

    def open_loop_editor(self):
        """Open the loop editor for the selected SCD or WAV file"""
        selected_items = self.library_controller.get_all_selected_items()
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
            from ui.conversion_manager import SimpleStatusDialog
            loading_dialog = SimpleStatusDialog("Loop Editor", self)
            loading_dialog.update_status("Loading loop editor...")
            loading_dialog.show()

            if ext.endswith('.wav'):
                loading_dialog.update_status("Loading WAV file...")
                success = self.loop_manager.load_wav_file(file_path)
            else:
                loading_dialog.update_status("Converting SCD to WAV...")
                success = self.loop_manager.load_file_for_editing(file_path)

            if not success:
                loading_dialog.close_dialog()
                show_themed_message(self, QMessageBox.Critical, "Load Error",
                                   "Failed to load audio file for editing.")
                return

            loading_dialog.update_status("Initializing loop editor...")
            from ui.loop_editor_dialog import LoopEditorDialog
            loop_editor = LoopEditorDialog(self.loop_manager, self)
            loading_dialog.close_dialog()
            loop_editor.exec_()
        except Exception as e:
            if 'loading_dialog' in locals():
                loading_dialog.close_dialog()
            show_themed_message(self, QMessageBox.Critical, "Loop Editor Error",
                               f"Failed to open loop editor:\n{str(e)}")

    # === Context Menus ===
    def show_file_list_context_menu(self, position):
        """Show context menu for main file list"""
        item = self.file_list.itemAt(position)
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        if not file_path or file_path.startswith("FOLDER_HEADER"):
            return
        
        menu = QMenu(self)
        
        # Export to KH Rando action
        export_action = menu.addAction("Export to KH Rando")
        export_action.triggered.connect(self.export_selected_to_kh_rando)
        
        menu.addSeparator()
        
        # Loop Editor action (only for SCD/WAV files with single selection)
        selected_items = [item for item in self.file_list.selectedItems() 
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        
        if len(selected_items) == 1:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.scd', '.wav']:
                loop_editor_action = menu.addAction("Open Loop Editor")
                loop_editor_action.triggered.connect(self.open_loop_editor)
                menu.addSeparator()
        
        # Rename action (single file only)
        if len(selected_items) == 1:
            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_file(file_path))
        
        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_files)
        
        menu.exec_(self.file_list.mapToGlobal(position))
    
    def show_kh_rando_context_menu(self, position):
        """Show context menu for KH Rando file list"""
        item = self.kh_rando_file_list.itemAt(position)
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        if not file_path or file_path.startswith("KH_CATEGORY_HEADER"):
            return
        
        menu = QMenu(self)
        
        # Loop Editor action (only for SCD/WAV files with single selection)
        selected_items = [item for item in self.kh_rando_file_list.selectedItems() 
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("KH_CATEGORY_HEADER")]
        
        if len(selected_items) == 1:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.scd', '.wav']:
                loop_editor_action = menu.addAction("Open Loop Editor")
                loop_editor_action.triggered.connect(self.open_loop_editor)
                menu.addSeparator()
        
        # Rename action (single file only)
        if len(selected_items) == 1:
            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_file(file_path))
        
        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_files)
        
        menu.exec_(self.kh_rando_file_list.mapToGlobal(position))
    
    def rename_file(self, file_path):
        """Rename a file"""
        from pathlib import Path
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        
        path = Path(file_path)
        if not path.exists():
            show_themed_message(self, QMessageBox.Warning, "File Not Found", 
                               "The file no longer exists.")
            return
        
        old_name = path.stem
        old_ext = path.suffix
        
        new_name, ok = QInputDialog.getText(
            self,
            "Rename File",
            f"Enter new name for '{path.name}':",
            QLineEdit.Normal,
            old_name
        )
        
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                return
            
            # Ensure extension is preserved
            new_file_path = path.parent / (new_name + old_ext)
            
            if new_file_path.exists():
                show_themed_message(self, QMessageBox.Warning, "File Exists", 
                                   f"A file named '{new_file_path.name}' already exists.")
                return
            
            try:
                path.rename(new_file_path)
                logging.info(f"Renamed file: {path} -> {new_file_path}")
                
                # The file watcher should detect this change, but we can also manually refresh
                # to ensure immediate update
                QTimer.singleShot(100, lambda: self.library_controller._on_file_removed(str(path)))
                QTimer.singleShot(200, lambda: self.library_controller._on_file_added(str(new_file_path)))
                
            except Exception as e:
                show_themed_message(self, QMessageBox.Critical, "Rename Error", 
                                   f"Failed to rename file:\n{str(e)}")
    
    # === Drag and Drop ===
    def start_file_drag(self, list_widget, supportedActions):
        """Custom drag start with transparency"""
        from PyQt5.QtCore import QMimeData
        from PyQt5.QtGui import QDrag
        
        # Get selected items
        selected_items = [item for item in list_widget.selectedItems()
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        
        if not selected_items:
            return
        
        # Create mime data with file paths
        mime_data = QMimeData()
        file_paths = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path:
                file_paths.append(file_path)
        
        # Store file paths as text
        mime_data.setText("\n".join(file_paths))
        
        # Create drag object
        drag = QDrag(list_widget)
        drag.setMimeData(mime_data)
        
        # Create simple drag pixmap with transparency and count
        pixmap_width = 200
        pixmap_height = 40
        pixmap = QPixmap(pixmap_width, pixmap_height)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent background
        painter.setOpacity(0.7)
        painter.setBrush(QColor(60, 60, 60))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, pixmap_width, pixmap_height, 5, 5)
        
        # Draw text
        painter.setOpacity(1.0)
        painter.setPen(Qt.white)
        from PyQt5.QtGui import QFont
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        
        if len(selected_items) == 1:
            text = f"📄 {selected_items[0].text()[:25]}"
        else:
            text = f"📄 {len(selected_items)} files"
        
        painter.drawText(10, 5, pixmap_width - 20, pixmap_height - 10, 
                        Qt.AlignLeft | Qt.AlignVCenter, text)
        
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        
        # Execute drag
        drag.exec_(Qt.CopyAction)
    
    def kh_rando_drag_enter_event(self, event):
        """Handle drag enter event for KH Rando list"""
        if event.mimeData().hasText() or event.source() == self.file_list:
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def kh_rando_drag_move_event(self, event):
        """Handle drag move event for KH Rando list with hover highlighting"""
        if not (event.mimeData().hasText() or event.source() == self.file_list):
            event.ignore()
            return
        
        # Auto-scroll if near edges
        drop_position = event.pos()
        list_height = self.kh_rando_file_list.height()
        scroll_margin = 30  # pixels from edge to trigger scroll
        
        if drop_position.y() < scroll_margin:
            # Near top - scroll up
            current_value = self.kh_rando_file_list.verticalScrollBar().value()
            self.kh_rando_file_list.verticalScrollBar().setValue(current_value - 5)
        elif drop_position.y() > list_height - scroll_margin:
            # Near bottom - scroll down
            current_value = self.kh_rando_file_list.verticalScrollBar().value()
            self.kh_rando_file_list.verticalScrollBar().setValue(current_value + 5)
        
        # Clear previous hover highlight
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        
        # Get item under cursor
        target_item = self.kh_rando_file_list.itemAt(drop_position)
        
        if target_item:
            item_data = target_item.data(Qt.UserRole)
            
            # Only highlight category headers
            if item_data and item_data.startswith("KH_CATEGORY_HEADER:"):
                # Make header bold and add background
                font = target_item.font()
                font.setBold(True)
                target_item.setFont(font)
                target_item.setBackground(QColor(86, 156, 214, 80))  # Blue highlight
                self._drag_hover_item = target_item
            # If hovering over a file, find and highlight its category
            elif item_data and not item_data.startswith("KH_CATEGORY_HEADER:"):
                # Find the category header above this file
                for i in range(self.kh_rando_file_list.row(target_item), -1, -1):
                    check_item = self.kh_rando_file_list.item(i)
                    check_data = check_item.data(Qt.UserRole)
                    if check_data and check_data.startswith("KH_CATEGORY_HEADER:"):
                        font = check_item.font()
                        font.setBold(True)
                        check_item.setFont(font)
                        check_item.setBackground(QColor(86, 156, 214, 80))
                        self._drag_hover_item = check_item
                        break
        
        event.acceptProposedAction()
    
    def kh_rando_drag_leave_event(self, event):
        """Handle drag leave event - clear hover highlighting"""
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        event.accept()
    
    def kh_rando_drop_event(self, event):
        """Handle drop event for KH Rando list - instant export to folder"""
        # Clear hover highlight
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        
        if not (event.mimeData().hasText() or event.source() == self.file_list):
            event.ignore()
            return
        
        # Get the dropped item position to determine target category
        drop_position = event.pos()
        target_item = self.kh_rando_file_list.itemAt(drop_position)
        
        # Get selected files from main list
        selected_items = [item for item in self.file_list.selectedItems()
                        if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        
        if not selected_items:
            event.ignore()
            return
        
        # Determine target category from drop position
        target_category = None
        if target_item:
            item_data = target_item.data(Qt.UserRole)
            if item_data:
                if item_data.startswith("KH_CATEGORY_HEADER:"):
                    # Dropped on category header
                    target_category = item_data.replace("KH_CATEGORY_HEADER:", "")
                else:
                    # Dropped on a file - find its category
                    for i in range(self.kh_rando_file_list.row(target_item), -1, -1):
                        check_item = self.kh_rando_file_list.item(i)
                        check_data = check_item.data(Qt.UserRole)
                        if check_data and check_data.startswith("KH_CATEGORY_HEADER:"):
                            target_category = check_data.replace("KH_CATEGORY_HEADER:", "")
                            break
        
        if not target_category:
            show_themed_message(self, QMessageBox.Information, "Drop Target", 
                               "Please drop files onto a KH Rando category folder.")
            event.ignore()
            return
        
        # Export files instantly to the target category
        self.export_files_to_category_instant(selected_items, target_category)
        event.acceptProposedAction()
    
    def export_files_to_category_instant(self, items, category):
        """Instantly export files to a specific KH Rando category (auto-convert if needed)"""
        from pathlib import Path
        
        # Get file paths and separate SCD vs non-SCD files
        scd_files = []
        files_to_convert = []
        
        for item in items:
            file_path = item.data(Qt.UserRole)
            if file_path and not file_path.startswith("FOLDER_HEADER") and os.path.exists(file_path):
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext == '.scd':
                    scd_files.append(file_path)
                elif file_ext in ['.wav', '.mp3', '.ogg', '.flac']:
                    files_to_convert.append(file_path)
        
        if not scd_files and not files_to_convert:
            return
        
        # Check if KH Rando folder is set
        if not self.config.kh_rando_folder or not os.path.exists(self.config.kh_rando_folder):
            show_themed_message(self, QMessageBox.Warning, "KH Rando Not Set", 
                               "Please set the KH Randomizer music folder first.")
            return
        
        # Show quality selection dialog only if conversion is needed
        selected_quality = 10  # Default quality
        if files_to_convert:
            from ui.conversion_manager import QualitySelectionDialog
            quality_dialog = QualitySelectionDialog(self)
            apply_title_bar_theming(quality_dialog)
            
            if quality_dialog.exec_() != QDialog.Accepted:
                return  # User cancelled
            
            selected_quality = quality_dialog.get_quality()
        
        # Prepare final file list (with conversions)
        final_files = scd_files.copy()
        converted_files = []
        
        # Convert non-SCD files if needed
        if files_to_convert:
            from ui.conversion_manager import SimpleStatusDialog
            status_dialog = SimpleStatusDialog("Converting Files", self)
            status_dialog.update_status(f"Converting {len(files_to_convert)} file(s) for export...")
            status_dialog.show()
            apply_title_bar_theming(status_dialog)
            QApplication.processEvents()
            
            for file_path in files_to_convert:
                try:
                    filename = os.path.basename(file_path)
                    status_dialog.update_status(f"Converting: {filename}")
                    QApplication.processEvents()
                    
                    # Convert to SCD in temp directory (mimic ConversionWorker._convert_to_scd logic)
                    file_ext = os.path.splitext(file_path)[1].lower()
                    temp_scd = os.path.join(tempfile.gettempdir(), f"{os.path.splitext(filename)[0]}.scd")
                    temp_wav = None
                    source_file = file_path
                    success = False
                    try:
                        if file_ext != '.wav':
                            fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_')
                            os.close(fd)
                            success_ffmpeg = self.converter.convert_with_ffmpeg(file_path, temp_wav, 'wav')
                            if not success_ffmpeg:
                                if temp_wav:
                                    try:
                                        os.remove(temp_wav)
                                    except:
                                        pass
                                logging.warning(f"FFmpeg conversion failed for: {filename}")
                                raise Exception("FFmpeg conversion failed")
                            source_file = temp_wav
                        # If original file was SCD, use as template
                        original_scd_template = file_path if file_ext == '.scd' else None
                        success = self.converter.convert_wav_to_scd(source_file, temp_scd, original_scd_template, selected_quality)
                    finally:
                        if temp_wav:
                            try:
                                os.remove(temp_wav)
                            except:
                                pass
                    if success and os.path.exists(temp_scd):
                        final_files.append(temp_scd)
                        converted_files.append(temp_scd)
                    else:
                        logging.warning(f"Conversion failed for: {filename}")
                except Exception as e:
                    logging.error(f"Error converting {file_path}: {e}")
            
            status_dialog.close_dialog()
        
        # Export all files to the target category
        if final_files:
            from ui.conversion_manager import SimpleStatusDialog
            export_dialog = SimpleStatusDialog("Exporting to KH Rando", self)
            export_dialog.update_status(f"Exporting {len(final_files)} file(s) to {category}...")
            export_dialog.show()
            apply_title_bar_theming(export_dialog)
            QApplication.processEvents()
            
            success_count = 0
            fail_count = 0
            
            for file_path in final_files:
                try:
                    filename = Path(file_path).name
                    export_dialog.update_status(f"Exporting: {filename}")
                    QApplication.processEvents()
                    
                    # Use the kh_rando_exporter to export to category
                    success = self.kh_rando_exporter.export_file(
                        file_path, category, self.config.kh_rando_folder
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        
                except Exception as e:
                    logging.error(f"Error exporting {file_path}: {e}")
                    fail_count += 1
            
            export_dialog.close_dialog()
            
            # Clean up converted temp files
            for temp_file in converted_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            # Show result
            if success_count > 0:
                message = f"Successfully exported {success_count} file(s) to {category}"
                if fail_count > 0:
                    message += f"\n{fail_count} file(s) failed to export"
                show_themed_message(self, QMessageBox.Information, "Export Complete", message)
                
                # Refresh the library
                self._refresh_duplicate_status()
                self._populate_kh_rando_list()
                self._update_kh_rando_section_counts()
            else:
                show_themed_message(self, QMessageBox.Warning, "Export Failed", 
                                   "Failed to export files. Check the log for details.")

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
        
        file_ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        self.label.setText(filename)
        self.setWindowTitle(f'SCDToolkit v{__version__} - {filename}')
        
        # Extract and display metadata
        self.display_file_metadata(file_path)
        
        # Update playlist
        self.playlist = self.library.get_playlist()
        self.current_playlist_index = self.library.find_file_index(file_path)
        
        # Track the actual WAV file being played (for loop manager sync)
        playback_wav_file = None
        
        # Handle different file types
        if file_ext == '.scd':
            wav_file = self.converter.convert_scd_to_wav(file_path)
            if wav_file:
                playback_wav_file = wav_file
                self.enable_playback_controls()
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText('Failed to convert SCD file.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
                
        elif file_ext == '.wav':
            playback_wav_file = file_path
            self.enable_playback_controls()
            media_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.player.setMedia(QMediaContent(media_url))
            
        else:  # MP3, OGG, FLAC
            wav_file = self.converter.convert_to_wav_temp(file_path)
            if wav_file:
                playback_wav_file = wav_file
                self.enable_playback_controls()
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(wav_file)))
            else:
                self.label.setText(f'Failed to convert {file_ext.upper()} file for playback.')
                self.metadata_label.setText('Failed to load file metadata.')
                return
        
        # Load the SAME WAV file into loop manager for duration/loop sync
        # This ensures loop markers match the actual playback duration
        if playback_wav_file:
            self.loop_manager.load_wav_file(playback_wav_file)
            # Store original SCD path if applicable (for save operations)
            if file_ext == '.scd':
                self.loop_manager.original_scd_path = file_path
            
            # Load audio into analyzer for real-time visualization
            if hasattr(self, 'audio_analyzer'):
                self.audio_analyzer.load_file(playback_wav_file)
        
        # Auto-play if requested
        if hasattr(self, 'auto_play_after_load') and self.auto_play_after_load:
            self.auto_play_after_load = False
            QTimer.singleShot(100, self.play_audio)
        
        # Update loop markers for the loaded file (with delay to allow QMediaPlayer to load)
        QTimer.singleShot(500, self.update_loop_markers)
        
        # Update library selection to highlight the loaded file (enables export/convert buttons)
        self.library_controller.update_library_selection(file_path)
        
        # Update button states now that we have a current file
        self.library_controller.on_library_selection_changed()
        
    def update_loop_markers(self):
        """Update loop markers on the seek slider"""
        print("DEBUG: update_loop_markers called")
        try:
            if self.current_file and self.loop_manager:
                print(f"DEBUG: current_file={self.current_file}, loop_manager exists")
                
                # Use the same method as loop editor for accuracy
                loop_start, loop_end = self.loop_manager.get_loop_points()
                file_info = self.loop_manager.get_file_info()
                
                print(f"DEBUG: get_loop_points() returned: start={loop_start}, end={loop_end}")
                print(f"DEBUG: file_info sample_rate={file_info.get('sample_rate', 'unknown')}")
                
                if loop_start >= 0 and loop_end > loop_start:
                    sample_rate = file_info.get('sample_rate', 44100)
                    total_samples = file_info.get('total_samples', 0)
                    
                    if sample_rate > 0:
                        # Convert to milliseconds for the slider
                        loop_start_ms = int((loop_start / sample_rate) * 1000)
                        loop_end_ms = int((loop_end / sample_rate) * 1000)
                        total_duration_ms = int((total_samples / sample_rate) * 1000)
                        
                        print(f"DEBUG: Setting markers - start: {loop_start_ms}ms, end: {loop_end_ms}ms")
                        self.seek_slider.set_loop_markers(loop_start_ms, loop_end_ms, total_duration_ms)
                        return
                        
            # Clear markers if no valid loop points
            print("DEBUG: Clearing loop markers - no valid loop points found")
            self.seek_slider.clear_loop_markers()
        except Exception as e:
            print(f"DEBUG: Error in update_loop_markers: {e}")
            self.seek_slider.clear_loop_markers()
            logging.warning(f"Error updating loop markers: {e}")
            self.seek_slider.clear_loop_markers()
        
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
        self.loop_btn.setEnabled(True)  # Enable loop button

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

    def toggle_loop(self):
        """Toggle loop mode on/off"""
        self.loop_enabled = not self.loop_enabled
        print(f"DEBUG: Loop toggled to {self.loop_enabled}")
        
        if self.loop_enabled:
            self.loop_btn.setIcon(create_icon("loop_on"))
            self.loop_btn.setToolTip("Loop On\n\nNote: Main window looping may not be 100% perfect due to Python/Qt constraints.\nFor perfect looping, use the Loop Editor (L key).")
            self.loop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a5a2a;
                    border: 2px solid #4a8a4a;
                }
                QPushButton:hover {
                    background-color: #3a7a3a;
                }
            """)
        else:
            self.loop_btn.setIcon(create_icon("loop"))
            self.loop_btn.setToolTip("Loop Off")
            self.loop_btn.setStyleSheet("")  # Reset to default style

    def previous_track(self):
        """Play previous track in full library playlist (not just visible UI)"""
        full_playlist = self.get_full_library_playlist()
        if len(full_playlist) > 1 and self.current_file in full_playlist:
            idx = full_playlist.index(self.current_file)
            if idx > 0:
                prev_idx = idx - 1
                self.current_playlist_index = prev_idx
                self.playlist = full_playlist
                self.load_file_path(full_playlist[prev_idx], auto_play=True)

    def next_track(self):
        """Play next track in full library playlist (not just visible UI)"""
        full_playlist = self.get_full_library_playlist()
        if len(full_playlist) > 1 and self.current_file in full_playlist:
            idx = full_playlist.index(self.current_file)
            if idx < len(full_playlist) - 1:
                next_idx = idx + 1
                self.current_playlist_index = next_idx
                self.playlist = full_playlist
                self.load_file_path(full_playlist[next_idx], auto_play=True)

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
        
    def check_loop_position(self):
        """High-frequency loop position checking for sample-accurate looping"""
        if not (self.loop_enabled and self.current_file and self.loop_manager and 
                self.player.state() == QMediaPlayer.PlayingState):
            return
            
        try:
            position = self.player.position()  # Current position in ms
            
            # Use the same method as loop editor for accuracy
            loop_start, loop_end = self.loop_manager.get_loop_points()
            file_info = self.loop_manager.get_file_info()
            
            if loop_start >= 0 and loop_end > loop_start:
                sample_rate = file_info.get('sample_rate', 44100)
                
                if sample_rate > 0:
                    # Use fractional milliseconds for better precision
                    loop_end_ms = (loop_end / sample_rate) * 1000.0
                    loop_start_ms = (loop_start / sample_rate) * 1000.0
                    
                    # Calculate sample-accurate tolerance with predictive compensation
                    sample_tolerance = 20  # samples - very tight tolerance 
                    tolerance_ms = (sample_tolerance / sample_rate) * 1000.0
                    
                    # Add predictive offset to compensate for timer/player lag (about 1-2ms)
                    predictive_offset_ms = 30  # Jump slightly earlier to compensate for lag
                    
                    # Get current position as float for better precision
                    current_pos = float(position)
                    
                    # If we've reached or passed the loop end point (with predictive offset), jump back to loop start
                    if current_pos >= (loop_end_ms - tolerance_ms - predictive_offset_ms):
                        # Round to nearest millisecond for setPosition (it only accepts int)
                        target_ms = int(round(loop_start_ms))
                        print(f"DEBUG: Loop end predicted at {current_pos:.1f}ms (target: {loop_end_ms:.1f}ms, trigger: {loop_end_ms - tolerance_ms - predictive_offset_ms:.1f}ms), jumping to {target_ms}ms")
                        self.player.setPosition(target_ms)
        except Exception as e:
            print(f"DEBUG: Error in loop checking: {e}")

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
        """Handle media status changes for auto-advance and looping"""
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            print(f"DEBUG: EndOfMedia detected, loop_enabled={self.loop_enabled}")
            if self.loop_enabled and self.current_file:
                # Handle looping - check if we have loop points
                try:
                    # Use the same method as loop editor for accuracy
                    loop_start, loop_end = self.loop_manager.get_loop_points()
                    file_info = self.loop_manager.get_file_info()
                    
                    if loop_start >= 0 and loop_end > loop_start:
                        sample_rate = file_info.get('sample_rate', 44100)
                        # Use precise calculation like the timer
                        loop_start_ms = int(round((loop_start / sample_rate) * 1000.0))
                        print(f"DEBUG: Looping back to loop start: {loop_start_ms}ms")
                        self.player.setPosition(loop_start_ms)
                        if self.player.state() != QMediaPlayer.PlayingState:
                            self.player.play()
                        return  # Don't advance to next track
                    
                    # No loop points, just restart from beginning
                    print("DEBUG: No loop points, restarting from beginning")
                    self.player.setPosition(0)
                    if self.player.state() != QMediaPlayer.PlayingState:
                        self.player.play()
                    return
                except Exception as e:
                    logging.warning(f"Error handling loop: {e}")
                    # Fallback - restart from beginning
                    self.player.setPosition(0)
                    if self.player.state() != QMediaPlayer.PlayingState:
                        self.player.play()
                    return
            
            # No looping or loop failed - advance to next track if available
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
    
    # === Visualizer methods ===
    def on_visualizer_changed(self, name):
        """Handle visualizer change"""
        logging.info(f"Visualizer changed to: {name}")
    
    def get_visualizer_audio_data(self):
        """Get real-time audio data for visualizer using FFT analysis"""
        import numpy as np
        
        # Get current state
        is_playing = self.player.state() == QMediaPlayer.PlayingState
        position_ms = self.player.position()
        
        # Calculate volume from player
        player_volume = self.player.volume() / 100.0
        
        # Get real spectrum data from audio analyzer
        if is_playing and position_ms > 0 and self.audio_analyzer.audio_data is not None:
            # Get FFT spectrum at current position
            spectrum = self.audio_analyzer.get_spectrum_at_position(position_ms)
            
            # Get actual RMS volume from audio
            volume = self.audio_analyzer.get_volume_at_position(position_ms)
            
            # Apply player volume scaling
            spectrum = spectrum * player_volume
            volume = volume * player_volume
        else:
            # Silent/stopped - return zeros
            spectrum = np.zeros(64)
            volume = 0.0
        
        return spectrum, volume, position_ms, is_playing
    
    def closeEvent(self, event):
        """Handle application close"""
        # Clean up thread
        if self.file_load_thread and self.file_load_thread.isRunning():
            self.file_load_thread.quit()
            self.file_load_thread.wait()
        
        # Stop file watcher
        if hasattr(self, 'file_watcher'):
            self.file_watcher.clear_watches()
            
        # Clean up temp files
        if getattr(self, 'converter', None):
            self.converter.cleanup_temp_files()
        event.accept()
    
    # File Watcher Methods
    def _perform_initial_scan(self):
        return self.library_controller.perform_initial_scan()
    
    def _start_file_watcher(self):
        """Start watching library folders for changes"""
        if not hasattr(self, 'file_watcher') or self.file_watcher is None:
            # File watcher not initialized yet, retry later
            QTimer.singleShot(50, self._start_file_watcher)
            return
        
        # Add library folders to watch
        folders_to_watch = list(self.config.library_folders)
        
        # Add KH Rando folder if set
        if self.config.kh_rando_folder:
            folders_to_watch.append(self.config.kh_rando_folder)
        
        # Start watching immediately (don't block on initial scan)
        self.file_watcher.add_watch_paths(folders_to_watch, self.config.scan_subdirs)
        
        # Scan initial files for tracking in the background (async, start immediately)
        QTimer.singleShot(0, lambda: self.file_watcher.scan_initial_files_async(folders_to_watch, self.config.scan_subdirs))
        
        logging.info(f"File watcher started for {len(folders_to_watch)} folders")
    
    def _on_file_removed(self, file_path: str):
        return self.library_controller._on_file_removed(file_path)
    
    def _on_directory_added(self, directory_path: str):
        return self.library_controller._on_directory_added(directory_path)
    
    def _on_directory_removed(self, directory_path: str):
        return self.library_controller._on_directory_removed(directory_path)
    
    def _on_file_modified(self, file_path: str):
        return self.library_controller._on_file_modified(file_path)
    
    def _remove_file_from_display(self, file_path: str):
        return self.library_controller._remove_file_from_display(file_path)
