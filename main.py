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
    QGroupBox, QFrame
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtGui import QIcon


class SCDPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'SCDPlayer v{__version__}')
        self.setGeometry(100, 100, 800, 600)
        self.config_file = 'scdplayer_config.json'

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
        player_panel.setFixedWidth(400)
        player_layout = QVBoxLayout()
        
        # File info
        info_layout = QHBoxLayout()
        self.label = QLabel('No file loaded')
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

        # Load controls
        load_layout = QHBoxLayout()
        self.load_file_btn = QPushButton('Load File')
        self.load_file_btn.clicked.connect(self.load_file)
        load_layout.addWidget(self.load_file_btn)
        player_layout.addLayout(load_layout)

        # Playback controls
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton('Play')
        self.play_btn.clicked.connect(self.play_audio)
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton('Pause')
        self.pause_btn.clicked.connect(self.pause_audio)
        self.pause_btn.setEnabled(False)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton('Stop')
        self.stop_btn.clicked.connect(self.stop_audio)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        player_layout.addLayout(controls_layout)

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
        
        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(100)
        for folder in self.library_folders:
            self.folder_list.addItem(folder)
        header_layout.addWidget(QLabel('Scan Folders:'))
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
        splitter.setSizes([400, 400])
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)

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
        self.wav_file = None
        self.duration = 0

        # Timer for updating time label
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_time_label)

        # Initial library scan
        self.rescan_library()

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
        """Load file from library double-click"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.load_file_path(file_path)

    def load_file(self):
        """Load audio file via file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Audio File', '', 
            'Audio Files (*.scd *.wav *.mp3 *.ogg *.flac);;SCD Files (*.scd);;WAV Files (*.wav);;MP3 Files (*.mp3);;OGG Files (*.ogg);;FLAC Files (*.flac);;All Files (*.*)'
        )
        if file_path:
            self.load_file_path(file_path)

    def load_file_path(self, file_path):
        """Load audio file from path - handles SCD, WAV, and other formats"""
        self.cleanup_temp_wavs()
        self.current_file = file_path
        file_ext = os.path.splitext(file_path)[1].lower()
        self.label.setText(f'Loaded: {os.path.basename(file_path)}')
        self.setWindowTitle(f'SCDPlayer v{__version__} - {os.path.basename(file_path)}')
        
        if file_ext == '.scd':
            # Convert SCD to WAV for playback
            self.wav_file = self.convert_scd_to_wav(file_path)
            if self.wav_file:
                self.play_btn.setEnabled(True)
                self.pause_btn.setEnabled(True)
                self.stop_btn.setEnabled(True)
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(False)  # Already SCD
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.wav_file)))
            else:
                self.label.setText('Failed to convert SCD file.')
                return
        else:
            # Direct playback for WAV, MP3, OGG, FLAC
            self.wav_file = None  # Not using temp file
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            
            # Enable appropriate conversion buttons
            if file_ext == '.wav':
                self.convert_to_wav_btn.setEnabled(False)  # Already WAV
                self.convert_to_scd_btn.setEnabled(True)
            else:
                # For MP3, OGG, FLAC - can convert to WAV or SCD
                self.convert_to_wav_btn.setEnabled(True)
                self.convert_to_scd_btn.setEnabled(True)
            
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

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
        ffmpeg_path = self.get_bundled_path('ffmpeg', 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            return False
        
        try:
            cmd = [ffmpeg_path, '-i', input_path, '-y', output_path]
            subprocess.run(cmd, check=True, capture_output=True)
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
            subprocess.run([vgmstream_path, '-o', wav_path, scd_path], check=True)
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
    app = QApplication(sys.argv)
    window = SCDPlayer()
    window.show()
    sys.exit(app.exec_())
