"""Music List JSON Editor for KH Randomizer"""
import json
import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QMessageBox, QHeaderView,
    QListWidget, QListWidgetItem, QInputDialog, QSplitter, QScrollArea,
    QWidget, QFrame, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from ui.dialogs import apply_title_bar_theming


class MusicListEditor(QDialog):
    """Editor for musiclist.json with category management"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KH Randomizer Music List Editor")
        self.resize(1000, 700)
        apply_title_bar_theming(self)
        
        self.musiclist_data = []
        self.musiclist_path = None
        self.default_musiclist_path = Path(__file__).parent.parent / "khpc_tools" / "musiclist.json"
        self.modified = False
        self.available_folders = []
        self.kh_rando_folder = None
        self.current_song = None
        
        self.setup_ui()
        self.load_musiclist()
        self.detect_folders()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Main background
        self.setStyleSheet("""
            QDialog {
                background-color: #212121;
            }
        """)
        
        # Header info
        header_layout = QHBoxLayout()
        self.path_label = QLabel("Music List: Not Loaded")
        self.path_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 11pt;
                padding: 5px;
            }
        """)
        header_layout.addWidget(self.path_label)
        
        header_layout.addStretch()
        
        locate_btn = QPushButton("Locate musiclist.json")
        locate_btn.clicked.connect(self.locate_musiclist)
        locate_btn.setStyleSheet(self.get_button_style())
        header_layout.addWidget(locate_btn)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setStyleSheet(self.get_button_style())
        header_layout.addWidget(reset_btn)
        
        layout.addLayout(header_layout)
        
        # Search/filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("QLabel { color: #e0e0e0; font-size: 10pt; }")
        search_layout.addWidget(search_label)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by song title or filename...")
        self.search_box.textChanged.connect(self.filter_songs)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #888;
            }
        """)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
        
        # Main content - splitter for song list and editor
        splitter = QSplitter(Qt.Horizontal)
        
        # Song list (cleaner than table)
        self.song_list = QListWidget()
        self.song_list.itemSelectionChanged.connect(self.on_song_selected)
        self.song_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                font-size: 10pt;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3a3a3a;
            }
            QListWidget::item:hover {
                background-color: #333;
            }
            QListWidget::item:selected {
                background-color: #444;
                color: #fff;
            }
        """)
        splitter.addWidget(self.song_list)
        
        # Category editor panel
        editor_widget = QWidget()
        editor_layout = QVBoxLayout()
        editor_widget.setStyleSheet("QWidget { background-color: #2a2a2a; }")
        
        # Song info card
        self.song_info_label = QLabel("Select a song to edit categories")
        self.song_info_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 11pt;
                font-weight: bold;
                padding: 10px;
                background-color: #333;
                border-radius: 5px;
            }
        """)
        self.song_info_label.setWordWrap(True)
        editor_layout.addWidget(self.song_info_label)
        
        # Folder weights header with Add Folder button
        weights_header_layout = QHBoxLayout()
        weights_label = QLabel("KH Randomizer Files:")
        weights_label.setStyleSheet("QLabel { color: #e0e0e0; font-size: 10pt; font-weight: bold; padding: 10px 5px 5px 5px; }")
        weights_header_layout.addWidget(weights_label)
        
        add_folder_btn = QPushButton("+ Add Folder")
        add_folder_btn.clicked.connect(self.add_new_folder)
        add_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #888;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        weights_header_layout.addWidget(add_folder_btn)
        weights_header_layout.addStretch()
        
        editor_layout.addLayout(weights_header_layout)
        
        # Scrollable area for sliders
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2a2a2a;
                border: none;
            }
        """)
        
        self.sliders_widget = QWidget()
        self.sliders_layout = QVBoxLayout()
        self.sliders_layout.setSpacing(5)
        self.sliders_widget.setLayout(self.sliders_layout)
        self.sliders_widget.setStyleSheet("QWidget { background-color: #2a2a2a; }")
        
        scroll_area.setWidget(self.sliders_widget)
        editor_layout.addWidget(scroll_area)
        
        # Store slider references
        self.folder_sliders = {}
        
        # Info label
        info_label = QLabel(
            "💡 Tip: You can add the same folder multiple times to increase its weight.\n"
            "Create custom folders in your KH Rando music folder and they'll appear in the dropdown."
        )
        info_label.setStyleSheet("""
            QLabel {
                color: #aaa;
                padding: 10px;
                background-color: #333;
                border-radius: 5px;
                border-left: 3px solid #666;
                font-size: 9pt;
            }
        """)
        info_label.setWordWrap(True)
        editor_layout.addWidget(info_label)
        
        editor_widget.setLayout(editor_layout)
        splitter.addWidget(editor_widget)
        splitter.setSizes([700, 500])
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_musiclist)
        save_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close_dialog)
        close_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def get_button_style(self):
        """Get button stylesheet - grey/white theme like main window"""
        return """
            QPushButton {
                background-color: #444;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #555;
                border: 1px solid #888;
            }
            QPushButton:pressed {
                background-color: #333;
            }
        """
    
    def detect_folders(self):
        """Detect available folders in KH Rando music directory"""
        if not self.kh_rando_folder or not os.path.exists(self.kh_rando_folder):
            # Try to get from config
            from utils.config import Config
            config = Config()
            config.load_settings()
            self.kh_rando_folder = config.kh_rando_folder
        
        self.available_folders = []
        
        if self.kh_rando_folder and os.path.exists(self.kh_rando_folder):
            try:
                # Get all subdirectories
                for item in os.listdir(self.kh_rando_folder):
                    item_path = os.path.join(self.kh_rando_folder, item)
                    if os.path.isdir(item_path):
                        self.available_folders.append(item)
                
                self.available_folders.sort()
                
                # Update dropdown
                self.folder_dropdown.clear()
                self.folder_dropdown.addItems(self.available_folders)
                
                logging.info(f"Detected {len(self.available_folders)} folders in KH Rando music directory")
            except Exception as e:
                logging.error(f"Failed to detect folders: {e}")
    
    def locate_musiclist(self):
        """Locate the musiclist.json file"""
        from ui.dialogs import show_themed_file_dialog
        
        # Try to find KH Rando folder from settings
        from utils.config import Config
        config = Config()
        config.load_settings()
        kh_rando_folder = config.kh_rando_folder
        
        # Default to parent of KH Rando music folder
        start_dir = ""
        if kh_rando_folder and os.path.exists(kh_rando_folder):
            parent_dir = Path(kh_rando_folder).parent
            start_dir = str(parent_dir / "musiclist.json")
        
        file_path = show_themed_file_dialog(
            self, "open", "Locate musiclist.json",
            start_dir, "JSON Files (*.json)"
        )
        
        if file_path:
            self.musiclist_path = file_path
            self.load_musiclist()
    
    def load_musiclist(self):
        """Load musiclist.json"""
        # Try to find it automatically first
        if not self.musiclist_path:
            from utils.config import Config
            config = Config()
            config.load_settings()
            kh_rando_folder = config.kh_rando_folder
            
            if kh_rando_folder and os.path.exists(kh_rando_folder):
                parent_dir = Path(kh_rando_folder).parent
                potential_path = parent_dir / "musiclist.json"
                if potential_path.exists():
                    self.musiclist_path = str(potential_path)
        
        if self.musiclist_path and os.path.exists(self.musiclist_path):
            try:
                with open(self.musiclist_path, 'r', encoding='utf-8') as f:
                    self.musiclist_data = json.load(f)
                self.path_label.setText(f"Music List: {self.musiclist_path}")
                self.populate_list()
                logging.info(f"Loaded musiclist.json from {self.musiclist_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load musiclist.json:\n{e}")
                logging.error(f"Failed to load musiclist.json: {e}")
        else:
            self.path_label.setText("Music List: Not Found - Click 'Locate musiclist.json'")
    
    def populate_list(self):
        """Populate the song list"""
        self.song_list.clear()
        
        for song in self.musiclist_data:
            title = song.get('title', 'Unknown')
            filename = song.get('filename', '')
            dmca = song.get('dmca', False)
            
            # Create display text
            display_text = f"{title}"
            if dmca:
                display_text += " ⚠️"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, song)  # Store song data
            
            self.song_list.addItem(item)
    
    def filter_songs(self, text):
        """Filter song list by search text"""
        for i in range(self.song_list.count()):
            item = self.song_list.item(i)
            song = item.data(Qt.UserRole)
            
            if not text:
                item.setHidden(False)
            else:
                title = song.get('title', '').lower()
                filename = song.get('filename', '').lower()
                show = text.lower() in title or text.lower() in filename
                item.setHidden(not show)
    
    def on_song_selected(self):
        """When a song is selected, show its weight sliders"""
        # Save current sliders to previously selected song before switching
        if hasattr(self, 'current_song') and self.current_song and self.folder_sliders:
            self.update_song_from_sliders(self.current_song)
        
        current_item = self.song_list.currentItem()
        if not current_item:
            return
        
        song = current_item.data(Qt.UserRole)
        if song:
            self.current_song = song
            
            # Update song info
            title = song.get('title', 'Unknown')
            filename = song.get('filename', '')
            self.song_info_label.setText(f"<b>{title}</b><br><small>{filename}</small>")
            
            # Create weight sliders
            self.create_sliders(song)
    
    def create_sliders(self, song_data):
        """Create weight sliders for all available folders"""
        # Clear existing sliders
        for i in reversed(range(self.sliders_layout.count())):
            widget = self.sliders_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        self.folder_sliders.clear()
        
        # Get current folder counts for this song (case-insensitive)
        current_types = song_data.get('type', [])
        folder_counts = {}
        for folder in current_types:
            # Normalize to lowercase for comparison
            folder_lower = folder.lower()
            folder_counts[folder_lower] = folder_counts.get(folder_lower, 0) + 1
        
        # Create slider for each available folder
        for folder in self.available_folders:
            slider_container = QWidget()
            slider_layout = QHBoxLayout()
            slider_layout.setContentsMargins(10, 5, 10, 5)
            slider_container.setLayout(slider_layout)
            slider_container.setStyleSheet("QWidget { background-color: #333; border-radius: 3px; }")
            
            # Folder name label (capitalize first letter for display)
            display_name = folder[0].upper() + folder[1:] if folder else folder
            folder_label = QLabel(display_name)
            folder_label.setFixedWidth(120)
            folder_label.setStyleSheet("QLabel { color: #e0e0e0; font-size: 10pt; }")
            slider_layout.addWidget(folder_label)
            
            # Slider
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(10)
            # Get count using lowercase folder name
            slider.setValue(folder_counts.get(folder.lower(), 0))
            slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    background: #2a2a2a;
                    height: 8px;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #888;
                    width: 16px;
                    margin: -4px 0;
                    border-radius: 8px;
                }
                QSlider::handle:horizontal:hover {
                    background: #aaa;
                }
                QSlider::sub-page:horizontal {
                    background: #666;
                    border-radius: 4px;
                }
            """)
            slider_layout.addWidget(slider, 1)
            
            # Value label (use lowercase for lookup)
            value_label = QLabel(str(folder_counts.get(folder.lower(), 0)))
            value_label.setFixedWidth(30)
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet("QLabel { color: #e0e0e0; font-size: 10pt; font-weight: bold; }")
            slider_layout.addWidget(value_label)
            
            # Connect slider to update label and mark as modified
            slider.valueChanged.connect(lambda val, lbl=value_label: lbl.setText(str(val)))
            slider.valueChanged.connect(lambda: setattr(self, 'modified', True))
            
            self.sliders_layout.addWidget(slider_container)
            self.folder_sliders[folder] = slider
        
        # Add stretch at the end
        self.sliders_layout.addStretch()
    
    def update_song_from_sliders(self, song_data):
        """Update song's type array based on slider values"""
        new_types = []
        
        for folder, slider in self.folder_sliders.items():
            count = slider.value()
            # Capitalize first letter when adding to JSON
            capitalized_folder = folder[0].upper() + folder[1:] if folder else folder
            for _ in range(count):
                new_types.append(capitalized_folder)
        
        song_data['type'] = new_types
        logging.info(f"Updated categories for {song_data.get('title')}: {new_types}")
    
    def add_new_folder(self):
        """Add a new folder to the KH Rando music directory"""
        if not self.kh_rando_folder or not os.path.exists(self.kh_rando_folder):
            QMessageBox.warning(
                self, 
                "No KH Rando Directory", 
                "KH Randomizer music directory not found. Please set it in the settings first."
            )
            return
        
        # Ask for folder name
        folder_name, ok = QInputDialog.getText(
            self,
            "Add New Folder",
            "Enter the name of the new folder:",
            QLineEdit.Normal,
            ""
        )
        
        if ok and folder_name:
            folder_name = folder_name.strip()
            if not folder_name:
                return
            
            # Create the folder path
            new_folder_path = os.path.join(self.kh_rando_folder, folder_name)
            
            # Check if it already exists
            if os.path.exists(new_folder_path):
                QMessageBox.warning(
                    self,
                    "Folder Exists",
                    f"The folder '{folder_name}' already exists."
                )
                return
            
            try:
                # Create the folder
                os.makedirs(new_folder_path)
                logging.info(f"Created new folder: {new_folder_path}")
                
                # Re-detect folders
                self.detect_folders()
                
                # Refresh the current song's sliders if one is selected
                current_item = self.song_list.currentItem()
                if current_item:
                    song = current_item.data(Qt.UserRole)
                    if song:
                        self.create_sliders(song)
                
                QMessageBox.information(
                    self,
                    "Folder Created",
                    f"Successfully created folder '{folder_name}' in the KH Randomizer music directory."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create folder:\n{e}"
                )
                logging.error(f"Failed to create folder: {e}")
    
    def save_musiclist(self):
        """Save changes to musiclist.json"""
        if not self.musiclist_path:
            QMessageBox.warning(self, "No File", "Please locate the musiclist.json file first.")
            return
        
        # Update current song from sliders if one is selected
        current_item = self.song_list.currentItem()
        if current_item:
            song = current_item.data(Qt.UserRole)
            if song and self.folder_sliders:
                self.update_song_from_sliders(song)
        
        try:
            # Backup original
            backup_path = self.musiclist_path + ".backup"
            if os.path.exists(self.musiclist_path):
                import shutil
                shutil.copy2(self.musiclist_path, backup_path)
            
            # Save new version
            with open(self.musiclist_path, 'w', encoding='utf-8') as f:
                json.dump(self.musiclist_data, f, indent=4, ensure_ascii=False)
            
            self.modified = False
            QMessageBox.information(self, "Saved", f"Music list saved successfully!\n\nBackup created: {backup_path}")
            logging.info(f"Saved musiclist.json to {self.musiclist_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save musiclist.json:\n{e}")
            logging.error(f"Failed to save musiclist.json: {e}")
    
    def reset_to_defaults(self):
        """Reset to default musiclist.json"""
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "This will reset the music list to default values.\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                with open(self.default_musiclist_path, 'r', encoding='utf-8') as f:
                    self.musiclist_data = json.load(f)
                self.populate_list()
                self.modified = True
                QMessageBox.information(self, "Reset", "Music list reset to defaults.")
                logging.info("Reset musiclist to defaults")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load defaults:\n{e}")
                logging.error(f"Failed to load default musiclist: {e}")
    
    def close_dialog(self):
        """Close dialog with unsaved changes check"""
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_musiclist()
                self.accept()
            elif reply == QMessageBox.Discard:
                self.accept()
        else:
            self.accept()
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_musiclist()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
