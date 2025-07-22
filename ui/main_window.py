"""Main application window for SCDPlayer"""
import os
import tempfile
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, 
    QLabel, QSlider, QSizePolicy, QListWidget, QCheckBox, QMessageBox, 
    QSplitter, QGroupBox, QProgressDialog
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor

from version import __version__
from ui.widgets import ScrollingLabel, create_icon
from ui.styles import DARK_THEME
from core.converter import AudioConverter
from core.threading import FileLoadThread
from core.library import AudioLibrary
from utils.config import Config
from utils.helpers import format_time


class SCDPlayer(QMainWindow):
    """Main SCDPlayer application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDPlayer v{__version__}')
        self.setGeometry(100, 100, 1000, 700)
        
        # Initialize components
        self.config = Config()
        self.converter = AudioConverter()
        self.current_file = None
        self.current_playlist_index = -1
        self.playlist = []
        
        # Initialize UI components
        self.setup_ui()
        self.setup_media_player()
        
        # Set window icon and style
        self.setWindowIcon(self.create_app_icon())
        self.setStyleSheet(DARK_THEME)
        
        # Load settings and initialize
        self.config.load_settings()
        self.library = AudioLibrary(self.file_list)
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs)
        
        # Threading components
        self.progress_dialog = None
        self.file_load_thread = None
        
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
        self.seek_slider.sliderMoved.connect(self.seek_position)
        player_layout.addWidget(self.seek_slider)

        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        
        self.prev_btn = self.create_control_button("previous", "Previous Track", self.previous_track)
        self.play_btn = self.create_control_button("play", "Play", self.play_audio)
        self.pause_btn = self.create_control_button("pause", "Pause", self.pause_audio)
        self.stop_btn = self.create_control_button("stop", "Stop", self.stop_audio)
        self.next_btn = self.create_control_button("next", "Next Track", self.next_track)
        
        for btn in [self.prev_btn, self.play_btn, self.pause_btn, self.stop_btn, self.next_btn]:
            controls_layout.addWidget(btn)
        
        player_layout.addLayout(controls_layout)
        player_layout.addSpacing(15)

        # Load controls
        load_layout = QHBoxLayout()
        self.load_file_btn = QPushButton('Load File')
        self.load_file_btn.clicked.connect(self.load_file)
        load_layout.addWidget(self.load_file_btn)
        player_layout.addLayout(load_layout)
        player_layout.addSpacing(15)

        # Conversion controls
        convert_layout = QHBoxLayout()
        self.convert_to_wav_btn = QPushButton('Convert to WAV')
        self.convert_to_wav_btn.clicked.connect(self.convert_current_to_wav)
        self.convert_to_wav_btn.setEnabled(False)
        convert_layout.addWidget(self.convert_to_wav_btn)
        
        self.convert_to_scd_btn = QPushButton('Convert to SCD')
        self.convert_to_scd_btn.clicked.connect(self.convert_current_to_scd)
        self.convert_to_scd_btn.setEnabled(False)
        convert_layout.addWidget(self.convert_to_scd_btn)
        player_layout.addLayout(convert_layout)

        player_layout.addStretch()
        player_panel.setLayout(player_layout)
        return player_panel
    
    def create_control_button(self, icon_type, tooltip, callback):
        """Create a playback control button"""
        btn = QPushButton()
        btn.setIcon(create_icon(icon_type))
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
        folder_controls.addWidget(remove_folder_btn)
        
        rescan_btn = QPushButton('Rescan')
        rescan_btn.clicked.connect(self.rescan_library)
        folder_controls.addWidget(rescan_btn)
        header_layout.addLayout(folder_controls)
        
        # Folder list
        header_layout.addWidget(QLabel('Scan Folders:'))
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(100)
        header_layout.addWidget(self.folder_list)
        
        # Scan subdirs toggle
        self.subdirs_checkbox = QCheckBox('Scan subdirectories')
        self.subdirs_checkbox.stateChanged.connect(self.toggle_subdirs)
        header_layout.addWidget(self.subdirs_checkbox)
        
        library_header.setLayout(header_layout)
        library_layout.addWidget(library_header)
        
        # File library
        library_layout.addWidget(QLabel('Audio Files (SCD, WAV, MP3, OGG, FLAC):'))
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.load_from_library)
        library_layout.addWidget(self.file_list)
        
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

    def create_app_icon(self):
        """Create application icon"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4a9eff"))
        
        # Simple music note icon
        painter.drawEllipse(8, 20, 8, 6)
        painter.drawRect(15, 10, 2, 16)
        painter.drawEllipse(17, 8, 6, 8)
        
        painter.end()
        return QIcon(pixmap)

    # === Library Management ===
    def add_library_folder(self):
        """Add a folder to the library"""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder and folder not in self.config.library_folders:
            self.config.library_folders.append(folder)
            self.folder_list.addItem(folder)
            self.config.save_settings()
            self.rescan_library()

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
        self.rescan_library()

    def rescan_library(self):
        """Rescan library folders"""
        self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs)
        
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
        
        # Show loading indicator
        self.progress_dialog = QProgressDialog("Loading audio file...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Loading")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()
        
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
        self.setWindowTitle(f'SCDPlayer v{__version__} - {filename}')
        
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
                self.progress_dialog.close()
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
                self.progress_dialog.close()
                return
            
        self.progress_dialog.close()
        
        # Auto-play if requested
        if hasattr(self, 'auto_play_after_load') and self.auto_play_after_load:
            self.auto_play_after_load = False
            QTimer.singleShot(100, self.play_audio)
        
    def on_file_load_error(self, error_msg):
        """Handle file load error"""
        self.label.setText(f'Error loading file: {error_msg}')
        if self.progress_dialog:
            self.progress_dialog.close()

    def enable_playback_controls(self):
        """Enable all playback control buttons"""
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.prev_btn.setEnabled(len(self.playlist) > 1)
        self.next_btn.setEnabled(len(self.playlist) > 1)

    # === Playback Controls ===
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

    def seek_position(self, position):
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
        if state == QMediaPlayer.StoppedState:
            self.timer.stop()

    def media_status_changed(self, status):
        """Handle media status changes for auto-advance"""
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            if len(self.playlist) > 1 and self.current_playlist_index < len(self.playlist) - 1:
                self.next_track()

    # === Conversion Features ===
    def convert_current_to_wav(self):
        """Convert currently loaded audio file to WAV and save"""
        if not self.current_file:
            QMessageBox.warning(self, 'No File Loaded', 'Please load an audio file first.')
            return
            
        file_ext = os.path.splitext(self.current_file)[1].lower()
        if file_ext == '.wav':
            QMessageBox.information(self, 'Already WAV', 'The loaded file is already in WAV format.')
            return
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, 'Save WAV As', 
            os.path.splitext(self.current_file)[0] + '.wav', 
            'WAV Files (*.wav)'
        )
        
        if save_path:
            if file_ext == '.scd':
                wav = self.converter.convert_scd_to_wav(self.current_file, out_path=save_path)
                if wav:
                    QMessageBox.information(self, 'Conversion Complete', f'WAV saved to: {save_path}')
                else:
                    QMessageBox.warning(self, 'Conversion Failed', 'Could not convert SCD to WAV.')
            else:
                success = self.converter.convert_with_ffmpeg(self.current_file, save_path, 'wav')
                if success:
                    QMessageBox.information(self, 'Conversion Complete', f'WAV saved to: {save_path}')
                else:
                    QMessageBox.warning(self, 'Conversion Failed', f'Could not convert {file_ext} to WAV.')

    def convert_current_to_scd(self):
        """Convert currently loaded audio file to SCD"""
        if not self.current_file:
            QMessageBox.warning(self, 'No File Loaded', 'Please load an audio file first.')
            return
            
        file_ext = os.path.splitext(self.current_file)[1].lower()
        if file_ext == '.scd':
            QMessageBox.information(self, 'Already SCD', 'The loaded file is already in SCD format.')
            return
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, 'Save SCD As', 
            os.path.splitext(self.current_file)[0] + '.scd', 
            'SCD Files (*.scd)'
        )
        
        if save_path:
            # Convert to WAV first if needed
            temp_wav = None
            source_file = self.current_file
            
            if file_ext != '.wav':
                fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_')
                os.close(fd)
                
                success = self.converter.convert_with_ffmpeg(self.current_file, temp_wav, 'wav')
                if not success:
                    QMessageBox.warning(self, 'Conversion Failed', 'Could not convert to WAV for SCD conversion.')
                    if temp_wav:
                        try:
                            os.remove(temp_wav)
                        except:
                            pass
                    return
                source_file = temp_wav
            
            success = self.converter.convert_wav_to_scd(source_file, save_path)
            
            # Cleanup temp file
            if temp_wav:
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            if success:
                QMessageBox.information(self, 'Conversion Complete', f'SCD saved to: {save_path}')
            else:
                QMessageBox.warning(self, 'Conversion Failed', 'WAV to SCD conversion is not yet fully implemented.')

    def closeEvent(self, event):
        """Handle application close"""
        # Clean up thread
        if self.file_load_thread and self.file_load_thread.isRunning():
            self.file_load_thread.quit()
            self.file_load_thread.wait()
        
        # Clean up progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            
        # Clean up temp files
        self.converter.cleanup_temp_files()
        event.accept()
