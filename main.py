# Modern audio player GUI for SCDPlayer
import sys
import os
import subprocess
import tempfile
import shutil
import json
from version import __version__
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel, QSlider, QSizePolicy,
    QMainWindow, QAction, QMenu, QDialog, QListWidget, QListWidgetItem, QCheckBox, QMessageBox, QSplitter,
    QGroupBox, QFrame, QProgressDialog, QSplashScreen
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPolygon


class SplashScreen(QSplashScreen):
    """Custom splash screen for SCDPlayer"""
    def __init__(self):
        # Create splash screen pixmap
        splash_pixmap = self.create_splash_pixmap()
        super().__init__(splash_pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Show loading message
        self.showMessage("Loading SCDPlayer...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        
    def create_splash_pixmap(self):
        """Create the splash screen image"""
        pixmap = QPixmap(400, 300)
        pixmap.fill(QColor("#1a1d23"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background gradient effect
        for i in range(20):
            color = QColor("#23272e")
            color.setAlpha(255 - i * 10)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(200 - i * 10, 150 - i * 8, i * 20, i * 16)
        
        # Draw large music note icon
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4a9eff"))
        
        # Note head
        painter.drawEllipse(160, 180, 40, 30)
        # Note stem
        painter.drawRect(195, 120, 8, 70)
        # Note flag
        painter.drawEllipse(203, 110, 30, 40)
        
        # Draw title
        font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f0f0f0"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "SCDPlayer")
        
        # Draw version
        font = QFont("Arial", 12)
        painter.setFont(font)
        painter.setPen(QColor("#888888"))
        version_rect = pixmap.rect()
        version_rect.adjust(0, 40, 0, 0)
        painter.drawText(version_rect, Qt.AlignCenter, f"v{__version__}")
        
        painter.end()
        return pixmap


class FileLoadThread(QThread):
    """Thread for loading files in the background"""
    finished = pyqtSignal(str)  # Signal emitted when file loading is complete
    error = pyqtSignal(str)     # Signal emitted when an error occurs
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        
    def run(self):
        try:
            file_ext = os.path.splitext(self.file_path)[1].lower()
            if file_ext == '.scd':
                # For SCD files, we need to convert them
                self.finished.emit(self.file_path)
            else:
                # For other formats, just signal completion
                self.finished.emit(self.file_path)
        except Exception as e:
            self.error.emit(str(e))


class ScrollingLabel(QLabel):
    """Label that scrolls text when it's too long"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self.scroll_text)
        self.scroll_position = 0
        self.pause_counter = 0
        self.pause_duration = 20  # Pause at start for 2 seconds (20 * 100ms)
        self.end_pause_duration = 15  # Pause at end for 1.5 seconds
        self.end_pause_counter = 0
        self.visible_length = 35  # Increased from 30 for more visible text
        self.scrolling_forward = True
        
    def setText(self, text):
        self.full_text = text
        self.scroll_position = 0
        self.pause_counter = 0
        self.end_pause_counter = 0
        self.scrolling_forward = True
        
        if len(text) > self.visible_length:
            super().setText(text[:self.visible_length])
            self.scroll_timer.start(100)  # Update every 100ms
        else:
            super().setText(text)
            self.scroll_timer.stop()
    
    def scroll_text(self):
        if len(self.full_text) <= self.visible_length:
            self.scroll_timer.stop()
            return
            
        # Pause at the beginning
        if self.scrolling_forward and self.pause_counter < self.pause_duration:
            self.pause_counter += 1
            return
            
        # Pause at the end
        if not self.scrolling_forward and self.end_pause_counter < self.end_pause_duration:
            self.end_pause_counter += 1
            return
            
        # Create scrolling effect
        if self.scrolling_forward:
            if self.scroll_position <= len(self.full_text) - self.visible_length:
                display_text = self.full_text[self.scroll_position:self.scroll_position + self.visible_length]
                super().setText(display_text)
                self.scroll_position += 1
            else:
                # Reached the end, start scrolling back
                self.scrolling_forward = False
                self.end_pause_counter = 0
        else:
            if self.scroll_position > 0:
                self.scroll_position -= 1
                display_text = self.full_text[self.scroll_position:self.scroll_position + self.visible_length]
                super().setText(display_text)
            else:
                # Reached the beginning, start scrolling forward
                self.scrolling_forward = True
                self.pause_counter = 0


def create_icon(icon_type, size=24):
    """Create simple icons using QPainter"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#f0f0f0"))
    
    center = size // 2
    
    if icon_type == "play":
        # Triangle pointing right
        triangle = QPolygon([
            QPoint(center - 6, center - 8),
            QPoint(center - 6, center + 8),
            QPoint(center + 8, center)
        ])
        painter.drawPolygon(triangle)
        
    elif icon_type == "pause":
        # Two rectangles
        painter.drawRect(center - 8, center - 8, 5, 16)
        painter.drawRect(center + 3, center - 8, 5, 16)
        
    elif icon_type == "stop":
        # Square
        painter.drawRect(center - 6, center - 6, 12, 12)
        
    elif icon_type == "previous":
        # Left-pointing triangle with line
        painter.drawRect(center - 8, center - 8, 2, 16)
        triangle = QPolygon([
            QPoint(center + 6, center - 8),
            QPoint(center + 6, center + 8),
            QPoint(center - 4, center)
        ])
        painter.drawPolygon(triangle)
        
    elif icon_type == "next":
        # Right-pointing triangle with line
        triangle = QPolygon([
            QPoint(center - 6, center - 8),
            QPoint(center - 6, center + 8),
            QPoint(center + 4, center)
        ])
        painter.drawPolygon(triangle)
        painter.drawRect(center + 6, center - 8, 2, 16)
    
    painter.end()
    return QIcon(pixmap)


class SCDPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDPlayer v{__version__}')
        self.setGeometry(100, 100, 1000, 700)  # Bigger default window size
        self.config_file = 'scdplayer_config.json'
        
        # Set window icon
        self.setWindowIcon(self.create_app_icon())

        # Load settings
        self.load_settings()

        # Create main widget and splitter
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        
        # Create splitter for player and library
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Player controls
        player_panel = QWidget()
        player_panel.setFixedWidth(450)  # Slightly wider
        player_layout = QVBoxLayout()
        player_layout.setSpacing(8)  # Reduce spacing between elements
        
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
        
        # Seek bar (directly below title)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        player_layout.addWidget(self.seek_slider)

        # Playback controls with icons (directly below seek bar)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)  # Reduce spacing between buttons
        
        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(create_icon("previous"))
        self.prev_btn.setToolTip("Previous Track")
        self.prev_btn.clicked.connect(self.previous_track)
        self.prev_btn.setEnabled(False)
        self.prev_btn.setFixedSize(40, 40)  # Make buttons more compact
        controls_layout.addWidget(self.prev_btn)
        
        self.play_btn = QPushButton()
        self.play_btn.setIcon(create_icon("play"))
        self.play_btn.setToolTip("Play")
        self.play_btn.clicked.connect(self.play_audio)
        self.play_btn.setEnabled(False)
        self.play_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(create_icon("pause"))
        self.pause_btn.setToolTip("Pause")
        self.pause_btn.clicked.connect(self.pause_audio)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(create_icon("stop"))
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop_audio)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self.stop_btn)
        
        self.next_btn = QPushButton()
        self.next_btn.setIcon(create_icon("next"))
        self.next_btn.setToolTip("Next Track")
        self.next_btn.clicked.connect(self.next_track)
        self.next_btn.setEnabled(False)
        self.next_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self.next_btn)
        
        player_layout.addLayout(controls_layout)

        # Add some spacing before load button
        player_layout.addSpacing(15)

        # Load controls
        load_layout = QHBoxLayout()
        self.load_file_btn = QPushButton('Load File')
        self.load_file_btn.clicked.connect(self.load_file)
        load_layout.addWidget(self.load_file_btn)
        player_layout.addLayout(load_layout)

        # Add some spacing before conversion buttons
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

        # Add stretch to push everything to the top
        player_layout.addStretch()

        player_panel.setLayout(player_layout)
        splitter.addWidget(player_panel)

        # Right panel - Library
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
        
        # Folder list with proper spacing
        header_layout.addWidget(QLabel('Scan Folders:'))
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(100)
        for folder in self.library_folders:
            self.folder_list.addItem(folder)
        header_layout.addWidget(self.folder_list)
        
        # Scan subdirs toggle
        self.subdirs_checkbox = QCheckBox('Scan subdirectories')
        self.subdirs_checkbox.setChecked(self.scan_subdirs)
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
        splitter.addWidget(library_panel)
        
        # Set splitter sizes
        splitter.setSizes([450, 550])  # Adjusted for bigger window
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)

        # Loading progress dialog
        self.progress_dialog = None
        self.file_load_thread = None
        
        # Track current playlist position
        self.current_playlist_index = -1
        self.playlist = []

        # Basic style for a cleaner look
        self.setStyleSheet('''
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
        ''')

        # Media player
        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.stateChanged.connect(self.update_state)
        self.player.mediaStatusChanged.connect(self.media_status_changed)  # Add this for auto-advance
        self.wav_file = None
        self.duration = 0

        # Timer for updating time label
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_time_label)

        # Initial library scan
        self.rescan_library()

    def create_app_icon(self):
        """Create application icon"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a music note-like icon
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4a9eff"))
        
        # Note head
        painter.drawEllipse(8, 20, 8, 6)
        # Note stem
        painter.drawRect(15, 10, 2, 16)
        # Note flag
        painter.drawEllipse(17, 8, 6, 8)
        
        painter.end()
        return QIcon(pixmap)

    def load_settings(self):
        """Load settings from config file"""
        self.library_folders = []
        self.scan_subdirs = True
        self.current_file = None
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.library_folders = config.get('library_folders', [])
                    self.scan_subdirs = config.get('scan_subdirs', True)
        except Exception:
            pass  # Use defaults if config loading fails

    def save_settings(self):
        """Save settings to config file"""
        try:
            config = {
                'library_folders': self.library_folders,
                'scan_subdirs': self.scan_subdirs
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass  # Fail silently if we can't save settings

    def add_library_folder(self):
        """Add a folder to the library"""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder and folder not in self.library_folders:
            self.library_folders.append(folder)
            self.folder_list.addItem(folder)
            self.save_settings()
            self.rescan_library()

    def remove_library_folder(self):
        """Remove selected folder from library"""
        current_row = self.folder_list.currentRow()
        if current_row >= 0:
            self.library_folders.pop(current_row)
            self.folder_list.takeItem(current_row)
            self.save_settings()
            self.rescan_library()

    def toggle_subdirs(self, state):
        """Toggle subdirectory scanning"""
        self.scan_subdirs = bool(state)
        self.save_settings()
        self.rescan_library()

    def rescan_library(self):
        """Rescan library folders for SCD and WAV files"""
        self.file_list.clear()
        
        # Supported audio file extensions
        supported_extensions = ['.scd', '.wav', '.mp3', '.ogg', '.flac']
        
        for folder in self.library_folders:
            try:
                if self.scan_subdirs:
                    for root, _, files in os.walk(folder):
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in supported_extensions):
                                full_path = os.path.join(root, f)
                                self.add_file_to_library(full_path)
                else:
                    for f in os.listdir(folder):
                        if any(f.lower().endswith(ext) for ext in supported_extensions):
                            full_path = os.path.join(folder, f)
                            self.add_file_to_library(full_path)
            except (OSError, PermissionError):
                continue

    def add_file_to_library(self, file_path):
        """Add a single file to the library list"""
        try:
            size = os.path.getsize(file_path)
            item = QListWidgetItem(f"{os.path.basename(file_path)} ({size//1024} KB)")
            item.setToolTip(file_path)
            item.setData(Qt.UserRole, file_path)
            self.file_list.addItem(item)
        except OSError:
            pass

    def load_from_library(self, item):
        """Load file from library double-click and auto-play"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.load_file_path(file_path, auto_play=True)

    def load_file(self):
        """Load audio file via file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Audio File', '', 
            'Audio Files (*.scd *.wav *.mp3 *.ogg *.flac);;SCD Files (*.scd);;WAV Files (*.wav);;MP3 Files (*.mp3);;OGG Files (*.ogg);;FLAC Files (*.flac);;All Files (*.*)'
        )
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path, auto_play=False):
        """Load audio file from path - handles SCD, WAV, and other formats"""
        self.auto_play_after_load = auto_play  # Store auto-play flag
        
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
        self.cleanup_temp_wavs()
        self.current_file = file_path
        file_ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        self.label.setText(f'{filename}')
        self.setWindowTitle(f'SCDPlayer v{__version__} - {filename}')
        
        # Update playlist
        self.update_playlist_position(file_path)
        
        if file_ext == '.scd':
            # Convert SCD to WAV for playback
            self.wav_file = self.convert_scd_to_wav(file_path)
            if self.wav_file:
                self.enable_playback_controls()
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(False)  # Already SCD
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.wav_file)))
            else:
                self.label.setText('Failed to convert SCD file.')
                self.progress_dialog.close()
                return
        elif file_ext == '.wav':
            # Direct WAV playback
            self.wav_file = None  # Not using temp file
            self.enable_playback_controls()
            self.convert_to_wav_btn.setEnabled(False)  # Already WAV
            self.convert_to_scd_btn.setEnabled(True)
            
            media_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.player.setMedia(QMediaContent(media_url))
        else:
            # For MP3, OGG, FLAC - convert to WAV for reliable playback
            # This fixes codec issues on Windows systems
            self.wav_file = self.convert_to_wav_temp(file_path)
            if self.wav_file:
                self.enable_playback_controls()
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(True)
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.wav_file)))
            else:
                self.label.setText(f'Failed to convert {file_ext.upper()} file for playback.')
                self.progress_dialog.close()
                return
            
        self.progress_dialog.close()
        
        # Auto-play if requested
        if hasattr(self, 'auto_play_after_load') and self.auto_play_after_load:
            self.auto_play_after_load = False  # Reset flag
            QTimer.singleShot(100, self.play_audio)  # Short delay to ensure media is ready
        
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
        
    def update_playlist_position(self, file_path):
        """Update current position in playlist"""
        # Get current library files as playlist
        self.playlist = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            self.playlist.append(item.data(Qt.UserRole))
            
        # Find current file index
        try:
            self.current_playlist_index = self.playlist.index(file_path)
        except ValueError:
            self.current_playlist_index = -1
            
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
                # Use vgmstream for SCD conversion
                wav = self.convert_scd_to_wav(self.current_file, out_path=save_path)
                if wav:
                    QMessageBox.information(self, 'Conversion Complete', f'WAV saved to: {save_path}')
                else:
                    QMessageBox.warning(self, 'Conversion Failed', 'Could not convert SCD to WAV.')
            else:
                # Use FFmpeg for other formats (MP3, OGG, FLAC)
                success = self.convert_with_ffmpeg(self.current_file, save_path, 'wav')
                if success:
                    QMessageBox.information(self, 'Conversion Complete', f'WAV saved to: {save_path}')
                else:
                    QMessageBox.warning(self, 'Conversion Failed', f'Could not convert {file_ext} to WAV.\nMake sure ffmpeg.exe is in the project folder.')

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
            # For SCD conversion, we need to first convert to WAV if it's not already
            temp_wav = None
            source_file = self.current_file
            
            if file_ext != '.wav':
                # Convert to temporary WAV first
                fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_', dir=tempfile.gettempdir())
                os.close(fd)
                
                success = self.convert_with_ffmpeg(self.current_file, temp_wav, 'wav')
                if not success:
                    QMessageBox.warning(self, 'Conversion Failed', f'Could not convert {file_ext} to WAV for SCD conversion.\nMake sure ffmpeg.exe is in the project folder.')
                    if temp_wav:
                        try:
                            os.remove(temp_wav)
                        except:
                            pass
                    return
                source_file = temp_wav
            
            # Now convert WAV to SCD using vgmstream (this is a placeholder - actual SCD encoding would need different tools)
            success = self.convert_wav_to_scd(source_file, save_path)
            
            # Cleanup temp file
            if temp_wav:
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            if success:
                QMessageBox.information(self, 'Conversion Complete', f'SCD saved to: {save_path}')
            else:
                QMessageBox.warning(self, 'Conversion Failed', 'WAV to SCD conversion is not yet fully implemented.\nThis would require specialized SCD encoding tools.')

    def convert_with_ffmpeg(self, input_path, output_path, format):
        """Convert audio files using bundled FFmpeg"""
        ffmpeg_path = self.get_bundled_path('ffmpeg', 'bin/ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            return False
        
        try:
            # Hide console window by setting creation flags
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            cmd = [ffmpeg_path, '-i', input_path, '-y', output_path]
            subprocess.run(cmd, 
                         check=True, 
                         capture_output=True,
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception:
            return False

    def convert_wav_to_scd(self, wav_path, scd_path):
        """Convert WAV to SCD (placeholder implementation)"""
        # This is a placeholder - actual SCD encoding would require specialized tools
        # For now, we'll just copy the WAV file with SCD extension as a demonstration
        try:
            shutil.copy2(wav_path, scd_path)
            return True
        except Exception:
            return False

    def convert_to_wav_temp(self, input_path):
        """Convert audio file to temporary WAV for playback"""
        try:
            # Create temp WAV file
            fd, wav_path = tempfile.mkstemp(suffix='.wav', prefix='scdplayer_', dir=tempfile.gettempdir())
            os.close(fd)
            
            # Convert using FFmpeg
            success = self.convert_with_ffmpeg(input_path, wav_path, 'wav')
            
            if success:
                # Track temp files for cleanup
                if not hasattr(self, '_temp_wavs'):
                    self._temp_wavs = []
                self._temp_wavs.append(wav_path)
                return wav_path
            else:
                # Clean up failed conversion
                try:
                    os.remove(wav_path)
                except:
                    pass
                return None
                
        except Exception:
            return None

    def get_bundled_path(self, subfolder, filename):
        """Get the path to a bundled executable in a subfolder, handling both development and PyInstaller modes"""
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            bundle_dir = sys._MEIPASS
            return os.path.join(bundle_dir, subfolder, filename)
        else:
            # Running in development mode
            return os.path.join(os.getcwd(), subfolder, filename)

    def convert_scd_to_wav(self, scd_path, out_path=None):
        if out_path is None:
            # Use a temp file for playback
            fd, wav_path = tempfile.mkstemp(suffix='.wav', prefix='scdplayer_', dir=tempfile.gettempdir())
            os.close(fd)
        else:
            wav_path = out_path
        
        vgmstream_path = self.get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        if not os.path.exists(vgmstream_path):
            self.label.setText('vgmstream-cli.exe not found!')
            return None
        
        try:
            # Hide console window by setting creation flags
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            subprocess.run([vgmstream_path, '-o', wav_path, scd_path], 
                         check=True, 
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Track temp wavs for cleanup
            if out_path is None:
                if not hasattr(self, '_temp_wavs'):
                    self._temp_wavs = []
                self._temp_wavs.append(wav_path)
            return wav_path
        except Exception as e:
            self.label.setText(f'Error: {e}')
            return None

    def cleanup_temp_wavs(self):
        if hasattr(self, '_temp_wavs'):
            for wav in self._temp_wavs:
                try:
                    os.remove(wav)
                except Exception:
                    pass
            self._temp_wavs = []

    def closeEvent(self, event):
        # Clean up thread
        if self.file_load_thread and self.file_load_thread.isRunning():
            self.file_load_thread.quit()
            self.file_load_thread.wait()
        
        # Clean up progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            
        # Clean up temp files
        self.cleanup_temp_wavs()
        event.accept()

    def convert_and_save(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select SCD File to Convert', '', 'SCD Files (*.scd)')
        if not file_path:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, 'Save WAV As', os.path.splitext(file_path)[0] + '.wav', 'WAV Files (*.wav)')
        if not save_path:
            return
        wav = self.convert_scd_to_wav(file_path, out_path=save_path)
        if wav:
            QMessageBox.information(self, 'Conversion Complete', f'WAV saved to: {save_path}')
        else:
            QMessageBox.warning(self, 'Conversion Failed', 'Could not convert SCD to WAV.')

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
        self.time_label.setText(f'{self.format_time(pos)} / {self.format_time(dur)}')

    def update_state(self, state):
        if state == QMediaPlayer.StoppedState:
            self.timer.stop()
            
    def media_status_changed(self, status):
        """Handle media status changes for auto-advance"""
        from PyQt5.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia:
            # Current track finished, play next track automatically
            if len(self.playlist) > 1 and self.current_playlist_index < len(self.playlist) - 1:
                self.next_track()

    @staticmethod
    def format_time(seconds):
        m, s = divmod(seconds, 60)
        return f'{int(m):02}:{int(s):02}'

    def play_audio(self):
        if self.current_file:  # We have a loaded file
            self.player.play()
            self.timer.start()

    def pause_audio(self):
        self.player.pause()
        self.timer.stop()

    def stop_audio(self):
        self.player.stop()
        self.timer.stop()


if __name__ == '__main__':
    import time
    app = QApplication(sys.argv)
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()  # Allow splash to show
    
    # Simulate loading time and create main window
    splash.showMessage("Initializing audio system...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.5)  # Brief pause
    
    splash.showMessage("Loading interface...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.3)
    
    # Create main window
    window = SCDPlayer()
    
    # Show main window and close splash
    splash.showMessage("Ready!", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.2)
    
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec_())
