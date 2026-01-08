"""Music Pack Creator Dialog UI for creating Kingdom Hearts II - Re:Fined Music Packs"""
import os
import logging
from pathlib import Path
from typing import List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QComboBox, QLineEdit, QTextEdit, QGroupBox, QSplitter,
    QMessageBox, QFileDialog, QProgressDialog, QRadioButton, QButtonGroup,
    QScrollArea, QWidget, QFrame
)
from PyQt5.QtCore import Qt, QTimer

from ui.dialogs import show_themed_message, apply_title_bar_theming
from ui.styles import DARK_THEME
from core.music_pack import TrackListParser, MusicPackMetadata, MusicPackExporter


class PerLanguageDialog(QDialog):
    """Dialog for editing per-language text (pack names or descriptions)"""
    
    def __init__(self, parent, field_type: str, english_value: str, current_values: dict = None):
        super().__init__(parent)
        self.field_type = field_type  # 'name' or 'description'
        self.english_value = english_value
        self.language_values = current_values or {}
        
        self.setWindowTitle(f"Per-Language {field_type.capitalize()}")
        self.setModal(True)
        self.setMinimumWidth(500)
        apply_title_bar_theming(self)
        self.setStyleSheet(DARK_THEME)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        info_label = QLabel(f"Set {self.field_type} for each language. Leave blank to use English value.")
        info_label.setStyleSheet("color: #888888; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Show English value as reference
        en_ref = QLabel(f"English: {self.english_value or '(not set)'}")
        en_ref.setStyleSheet("color: #4A9EFF; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(en_ref)
        
        # Language fields
        self.lang_inputs = {}
        languages = [
            ('it', 'Italian'),
            ('gr', 'German'),
            ('fr', 'French'),
            ('sp', 'Spanish')
        ]
        
        for lang_code, lang_name in languages:
            lang_layout = QHBoxLayout()
            label = QLabel(f"{lang_name}:")
            label.setMinimumWidth(80)
            lang_layout.addWidget(label)
            
            if self.field_type == 'description':
                input_field = QTextEdit()
                input_field.setMaximumHeight(60)
                input_field.setPlaceholderText(f"{lang_name} {self.field_type}")
                if lang_code in self.language_values:
                    input_field.setPlainText(self.language_values[lang_code])
            else:
                input_field = QLineEdit()
                input_field.setPlaceholderText(f"{lang_name} {self.field_type}")
                if lang_code in self.language_values:
                    input_field.setText(self.language_values[lang_code])
            
            self.lang_inputs[lang_code] = input_field
            lang_layout.addWidget(input_field)
            layout.addLayout(lang_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def clear_all(self):
        """Clear all language fields"""
        for input_field in self.lang_inputs.values():
            if isinstance(input_field, QTextEdit):
                input_field.clear()
            else:
                input_field.clear()
    
    def get_values(self) -> dict:
        """Get the language values from inputs (blank fields won't be included, allowing English fallback)"""
        values = {}
        for lang_code, input_field in self.lang_inputs.items():
            if isinstance(input_field, QTextEdit):
                text = input_field.toPlainText().strip()
            else:
                text = input_field.text().strip()
            
            # Only include non-empty values - blank fields will use English as fallback
            if text:
                values[lang_code] = text
        return values


class MusicPackCreatorDialog(QDialog):
    """Dialog for creating Kingdom Hearts II - Re:Fined Music Pack mods"""
    
    def __init__(self, parent, library_files: List[str]):
        """
        Initialize Music Pack Creator dialog.
        
        Args:
            parent: Parent window (SCDToolkit main window)
            library_files: List of file paths from the loaded library
        """
        super().__init__(parent)
        self.parent_window = parent
        self.library_files = library_files
        self.track_assignments = {}  # Maps filename -> source_file_path
        
        self.setWindowTitle('Music Pack Creator - Kingdom Hearts II - Re:Fined')
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(DARK_THEME)
        
        # Make dialog non-modal so main window can be used
        self.setModal(False)
        
        # Parse track list
        track_list_path = Path(__file__).parent.parent / 'music_pack_creator' / 'TrackList.txt'
        self.vanilla_tracks = TrackListParser.parse_track_list(str(track_list_path))
        
        # Initialize exporter
        template_path = Path(__file__).parent.parent / 'music_pack_creator'
        self.exporter = MusicPackExporter(str(template_path))
        
        self.setup_ui()
        apply_title_bar_theming(self)
    
    def setup_ui(self):
        """Set up the user interface"""
        main_layout = QVBoxLayout()
        
        # Header
        header = QLabel("Create a Music Pack for Kingdom Hearts II - Re:Fined")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(header)
        
        # Instructions
        instructions = QLabel(
            "Assign songs from your library to vanilla KH2 tracks. "
            "Use the dropdown menus to select source files, or drag and drop files from your library."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 5px; color: #aaaaaa;")
        main_layout.addWidget(instructions)
        
        # Create splitter for library and track assignment
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Library files
        library_panel = self.create_library_panel()
        splitter.addWidget(library_panel)
        
        # Right side: Track assignments
        assignment_panel = self.create_assignment_panel()
        splitter.addWidget(assignment_panel)
        
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)
        
        # Pack metadata
        metadata_group = self.create_metadata_panel()
        main_layout.addWidget(metadata_group)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        open_btn = QPushButton('Open Music Pack...')
        open_btn.clicked.connect(self.load_existing_pack)
        button_layout.addWidget(open_btn)

        clear_btn = QPushButton('Clear All Assignments')
        clear_btn.clicked.connect(self.clear_all_assignments)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        export_btn = QPushButton('Export Music Pack')
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #0077ee;
            }
        """)
        export_btn.clicked.connect(self.export_music_pack)
        button_layout.addWidget(export_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def create_library_panel(self) -> QWidget:
        """Create the library files panel"""
        panel = QGroupBox("Your Library")
        layout = QVBoxLayout()
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Filter library files...")
        self.library_search.textChanged.connect(self.filter_library)
        search_layout.addWidget(self.library_search)
        layout.addLayout(search_layout)
        
        # File list
        self.library_list = QListWidget()
        self.library_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.library_list.setDragEnabled(True)
        self.library_list.itemDoubleClicked.connect(self.on_library_double_click)
        layout.addWidget(self.library_list)
        
        # Stats (create before populate so it can be updated)
        self.library_stats_label = QLabel(f"Total files: {len(self.library_files)}")
        self.library_stats_label.setStyleSheet("color: #888888; padding: 5px;")
        layout.addWidget(self.library_stats_label)
        
        # Populate after stats label is created
        self.populate_library_list()
        
        panel.setLayout(layout)
        return panel
    
    def create_assignment_panel(self) -> QWidget:
        """Create the track assignment panel"""
        panel = QGroupBox("Track Assignments")
        layout = QVBoxLayout()
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.track_search = QLineEdit()
        self.track_search.setPlaceholderText("Filter tracks...")
        self.track_search.textChanged.connect(self.filter_tracks)
        search_layout.addWidget(self.track_search)
        layout.addLayout(search_layout)
        
        # Scrollable track list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        self.tracks_layout = QVBoxLayout()
        self.tracks_layout.setSpacing(5)
        
        # Create track assignment rows
        self.track_rows = {}
        for track_name, filename in self.vanilla_tracks:
            row = self.create_track_row(track_name, filename)
            self.tracks_layout.addWidget(row)
            self.track_rows[filename] = row
        
        scroll_widget.setLayout(self.tracks_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Stats
        self.assignment_stats_label = QLabel("Assigned: 0 / {}".format(len(self.vanilla_tracks)))
        self.assignment_stats_label.setStyleSheet("color: #888888; padding: 5px;")
        layout.addWidget(self.assignment_stats_label)
        
        panel.setLayout(layout)
        return panel
    
    def create_track_row(self, track_name: str, filename: str) -> QWidget:
        """Create a single track assignment row"""
        row = QFrame()
        row.setFrameStyle(QFrame.StyledPanel)
        row.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(5)
        
        # Track info - single line with filename in parentheses
        name_label = QLabel(f"{track_name}")
        name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        name_label.setMinimumWidth(250)
        name_label.setWordWrap(False)
        name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(name_label, stretch=2)
        
        # Assignment dropdown
        combo = QComboBox()
        combo.addItem("-- Not Assigned --", None)
        
        # Lazy load combo items - only populate when first opened
        combo.setProperty('_populated', False)
        combo.setProperty('_filename', filename)
        
        def populate_combo(combo_ref):
            if not combo_ref.property('_populated'):
                # Add all library files
                for file_path in self.library_files:
                    display_name = os.path.basename(file_path)
                    combo_ref.addItem(display_name, file_path)
                combo_ref.setProperty('_populated', True)
        
        # Populate on first click
        def on_combo_show():
            populate_combo(combo)
        
        combo.showPopup = lambda c=combo, orig=combo.showPopup: (populate_combo(c), orig())
        
        combo.currentIndexChanged.connect(lambda idx, fn=filename: self.on_assignment_changed(fn, idx))
        combo.setMinimumWidth(300)
        combo.setMinimumHeight(26)
        combo.setStyleSheet("QComboBox { font-size: 11px; padding: 3px; }")
        layout.addWidget(combo, stretch=3)
        
        # Clear button
        clear_btn = QPushButton('×')
        clear_btn.setMaximumSize(24, 24)
        clear_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        clear_btn.setToolTip('Clear assignment')
        clear_btn.clicked.connect(lambda checked, fn=filename: self.clear_assignment(fn))
        layout.addWidget(clear_btn)
        
        row.setLayout(layout)
        row.setMaximumHeight(32)
        
        # Store references
        row.combo = combo
        row.filename = filename
        row.track_name = track_name
        row.name_label = name_label
        
        # Enable drop
        row.setAcceptDrops(True)
        row.dragEnterEvent = lambda event, fn=filename: self.track_drag_enter(event, fn)
        row.dropEvent = lambda event, fn=filename: self.track_drop(event, fn)
        
        return row
    
    def create_metadata_panel(self) -> QWidget:
        """Create the pack metadata panel"""
        panel = QGroupBox("Music Pack Information")
        layout = QVBoxLayout()
        
        # Slot selection
        slot_layout = QHBoxLayout()
        slot_layout.addWidget(QLabel("Slot:"))
        
        self.slot_group = QButtonGroup()
        self.slot0_radio = QRadioButton("Slot 0 (Replaces Vanilla)")
        self.slot1_radio = QRadioButton("Slot 1")
        self.slot2_radio = QRadioButton("Slot 2")
        self.slot12_radio = QRadioButton("Slot 1+2 (2 Files)")
        self.slot1_radio.setChecked(True)
        self.slot_group.addButton(self.slot0_radio)
        self.slot_group.addButton(self.slot1_radio)
        self.slot_group.addButton(self.slot2_radio)
        self.slot_group.addButton(self.slot12_radio)
        
        slot_layout.addWidget(self.slot0_radio)
        slot_layout.addWidget(self.slot1_radio)
        slot_layout.addWidget(self.slot2_radio)
        slot_layout.addWidget(self.slot12_radio)
        slot_layout.addStretch()
        layout.addLayout(slot_layout)
        
        # Side-by-side layout for mod.yml and sys.yml
        horizontal_splitter = QSplitter(Qt.Horizontal)
        
        # === OpenKH Mod Manager Info (mod.yml) ===
        mod_group = QGroupBox("Mod Manager Info (mod.yml)")
        mod_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        mod_layout = QVBoxLayout()
        
        # Mod title
        mod_title_layout = QHBoxLayout()
        mod_title_layout.addWidget(QLabel("Title:"))
        self.mod_title_input = QLineEdit()
        self.mod_title_input.setPlaceholderText("My Custom Music Pack")
        mod_title_layout.addWidget(self.mod_title_input)
        mod_layout.addLayout(mod_title_layout)
        
        # Mod author
        mod_author_layout = QHBoxLayout()
        mod_author_layout.addWidget(QLabel("Author:"))
        self.mod_author_input = QLineEdit()
        self.mod_author_input.setPlaceholderText("Your Name")
        mod_author_layout.addWidget(self.mod_author_input)
        mod_layout.addLayout(mod_author_layout)
        
        # Mod description
        mod_desc_layout = QVBoxLayout()
        mod_desc_layout.addWidget(QLabel("Description:"))
        self.mod_description_input = QTextEdit()
        self.mod_description_input.setPlaceholderText("A custom music pack for Kingdom Hearts II - Re:Fined")
        self.mod_description_input.setMaximumHeight(60)
        mod_desc_layout.addWidget(self.mod_description_input)
        mod_layout.addLayout(mod_desc_layout)
        
        mod_group.setLayout(mod_layout)
        horizontal_splitter.addWidget(mod_group)
        
        # === In-Game Info (sys.yml) ===
        game_group = QGroupBox("In-Game Info (sys.yml)")
        game_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        game_layout = QVBoxLayout()
        
        info_label = QLabel("Displayed in-game menu")
        info_label.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        game_layout.addWidget(info_label)
        
        # Pack Name with per-language button
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Pack Name (EN):"))
        self.game_name_input = QLineEdit()
        self.game_name_input.setPlaceholderText("My Custom Music Pack")
        name_layout.addWidget(self.game_name_input)
        
        self.name_lang_btn = QPushButton("Set Per Language")
        self.name_lang_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4A9EFF;
                border: none;
                text-decoration: underline;
                padding: 2px 8px;
            }
            QPushButton:hover {
                color: #6AB0FF;
            }
        """)
        self.name_lang_btn.setCursor(Qt.PointingHandCursor)
        self.name_lang_btn.clicked.connect(self.open_name_lang_dialog)
        name_layout.addWidget(self.name_lang_btn)
        
        self.name_lang_indicator = QLabel("Using English")
        self.name_lang_indicator.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        name_layout.addWidget(self.name_lang_indicator)
        
        game_layout.addLayout(name_layout)
        
        # Description with per-language button
        desc_layout = QVBoxLayout()
        desc_header = QHBoxLayout()
        desc_header.addWidget(QLabel("Description (EN):"))
        
        self.desc_lang_btn = QPushButton("Set Per Language")
        self.desc_lang_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4A9EFF;
                border: none;
                text-decoration: underline;
                padding: 2px 8px;
            }
            QPushButton:hover {
                color: #6AB0FF;
            }
        """)
        self.desc_lang_btn.setCursor(Qt.PointingHandCursor)
        self.desc_lang_btn.clicked.connect(self.open_desc_lang_dialog)
        desc_header.addWidget(self.desc_lang_btn)
        
        self.desc_lang_indicator = QLabel("Using English")
        self.desc_lang_indicator.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        desc_header.addWidget(self.desc_lang_indicator)
        desc_header.addStretch()
        
        desc_layout.addLayout(desc_header)
        
        self.game_description_input = QTextEdit()
        self.game_description_input.setPlaceholderText("This is the description of your Custom Music Pack!")
        self.game_description_input.setMaximumHeight(60)
        desc_layout.addWidget(self.game_description_input)
        game_layout.addLayout(desc_layout)
        
        game_group.setLayout(game_layout)
        horizontal_splitter.addWidget(game_group)
        
        horizontal_splitter.setSizes([500, 500])
        layout.addWidget(horizontal_splitter)
        
        # Initialize per-language storage
        self.name_lang_values = {}
        self.desc_lang_values = {}
        
        panel.setLayout(layout)
        return panel
    
    def open_name_lang_dialog(self):
        """Open dialog to set per-language pack names"""
        english_value = self.game_name_input.text().strip()
        if not english_value:
            show_themed_message(self, QMessageBox.Warning, 'Missing English Value',
                              'Please enter an English pack name first.')
            return
        
        dialog = PerLanguageDialog(self, 'name', english_value, self.name_lang_values)
        if dialog.exec_() == QDialog.Accepted:
            self.name_lang_values = dialog.get_values()
            self.update_lang_indicator(self.name_lang_indicator, self.name_lang_values)
    
    def open_desc_lang_dialog(self):
        """Open dialog to set per-language descriptions"""
        english_value = self.game_description_input.toPlainText().strip()
        if not english_value:
            show_themed_message(self, QMessageBox.Warning, 'Missing English Value',
                              'Please enter an English description first.')
            return
        
        dialog = PerLanguageDialog(self, 'description', english_value, self.desc_lang_values)
        if dialog.exec_() == QDialog.Accepted:
            self.desc_lang_values = dialog.get_values()
            self.update_lang_indicator(self.desc_lang_indicator, self.desc_lang_values)
    
    def update_lang_indicator(self, indicator: QLabel, lang_values: dict):
        """Update the language indicator label"""
        if lang_values:
            indicator.setText("Per Language")
            indicator.setStyleSheet("color: #4A9EFF; font-size: 10px; font-weight: bold;")
        else:
            indicator.setText("Using English")
            indicator.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
    
    def populate_library_list(self):
        """Populate the library list with files"""
        self.library_list.clear()
        scd_count = 0
        other_count = 0
        
        for file_path in self.library_files:
            # Show all audio files, will convert if needed
            filename = os.path.basename(file_path)
            item = QListWidgetItem(filename)
            item.setData(Qt.UserRole, file_path)
            
            # Add visual indicator for non-SCD files that need conversion
            if not file_path.lower().endswith('.scd'):
                item.setText(f"{filename} [will convert]")
                item.setToolTip(f"{filename}\nWill be converted to SCD during export")
                other_count += 1
            else:
                scd_count += 1
            
            self.library_list.addItem(item)
        
        # Update stats
        self.library_stats_label.setText(
            f"Total files: {len(self.library_files)} ({scd_count} SCD, {other_count} other)"
        )
    
    def filter_library(self, search_text: str):
        """Filter library files based on search text"""
        for i in range(self.library_list.count()):
            item = self.library_list.item(i)
            visible = search_text.lower() in item.text().lower()
            item.setHidden(not visible)
    
    def filter_tracks(self, search_text: str):
        """Filter track rows based on search text"""
        search_lower = search_text.lower()
        for filename, row in self.track_rows.items():
            visible = (search_lower in row.track_name.lower() or 
                      search_lower in filename.lower())
            row.setVisible(visible)
    
    def track_drag_enter(self, event, filename: str):
        """Handle drag enter event for track rows"""
        event.acceptProposedAction()
    
    def track_drop(self, event, filename: str):
        """Handle drop event for track rows"""
        # Get the currently selected file from library
        selected_items = self.library_list.selectedItems()
        if selected_items:
            source_file = selected_items[0].data(Qt.UserRole)
            self.assign_track(filename, source_file)
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def on_library_double_click(self, item):
        """Handle double-click on library item - play in main window"""
        file_path = item.data(Qt.UserRole)
        if file_path and self.parent_window:
            # Load and play the file in the main window
            self.parent_window.load_file_path(file_path, auto_play=True)
    
    def on_assignment_changed(self, filename: str, combo_index: int):
        """Handle assignment dropdown change"""
        row = self.track_rows.get(filename)
        if row:
            source_file = row.combo.itemData(combo_index)
            if source_file:
                self.track_assignments[filename] = source_file
            else:
                self.track_assignments.pop(filename, None)
            self.update_stats()
    
    def assign_track(self, filename: str, source_file: str):
        """Assign a source file to a track"""
        self.track_assignments[filename] = source_file
        
        # Update the combo box
        row = self.track_rows.get(filename)
        if row:
            # Ensure combo is populated before searching
            if not row.combo.property('_populated'):
                for file_path in self.library_files:
                    display_name = os.path.basename(file_path)
                    row.combo.addItem(display_name, file_path)
                row.combo.setProperty('_populated', True)
            
            for i in range(row.combo.count()):
                if row.combo.itemData(i) == source_file:
                    row.combo.setCurrentIndex(i)
                    break
        
        self.update_stats()
    
    def clear_assignment(self, filename: str):
        """Clear a track assignment"""
        self.track_assignments.pop(filename, None)
        row = self.track_rows.get(filename)
        if row:
            row.combo.setCurrentIndex(0)
        self.update_stats()
    
    def clear_all_assignments(self):
        """Clear all track assignments"""
        reply = QMessageBox.question(
            self, 'Clear All',
            'Are you sure you want to clear all track assignments?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.reset_assignments()

    def reset_assignments(self):
        """Reset assignments without prompt"""
        self.track_assignments.clear()
        for row in self.track_rows.values():
            row.combo.setCurrentIndex(0)
        self.update_stats()
    
    def update_stats(self):
        """Update assignment statistics"""
        assigned_count = len(self.track_assignments)
        total_count = len(self.vanilla_tracks)
        self.assignment_stats_label.setText(f"Assigned: {assigned_count} / {total_count}")
    
    def export_music_pack(self):
        """Export the music pack as a ZIP file"""
        # Validate inputs
        mod_title = self.mod_title_input.text().strip()
        game_name_en = self.game_name_input.text().strip()
        
        if not mod_title:
            show_themed_message(self, QMessageBox.Warning, 'Missing Information', 
                              'Please enter a mod title (for OpenKH Mod Manager).')
            return
        
        if not game_name_en:
            show_themed_message(self, QMessageBox.Warning, 'Missing Information',
                              'Please enter an English in-game pack name.')
            return
        
        if not self.track_assignments:
            show_themed_message(self, QMessageBox.Warning, 'No Tracks Assigned',
                              'Please assign at least one track before exporting.')
            return
        
        # Determine slot(s)
        if self.slot0_radio.isChecked():
            slots = [0]
        elif self.slot1_radio.isChecked():
            slots = [1]
        elif self.slot2_radio.isChecked():
            slots = [2]
        else:  # slot12_radio
            slots = [1, 2]
        
        # Get output location
        base_name = mod_title.replace(' ', '_')
        if len(slots) == 1:
            default_filename = f"{base_name}-SL{slots[0]}.zip"
        else:
            default_filename = f"{base_name}.zip"
        
        output_file = QFileDialog.getSaveFileName(
            self, 'Save Music Pack', default_filename,
            'ZIP Files (*.zip);;All Files (*.*)'
        )[0]
        
        if not output_file:
            return
        
        # For Slot 1+2, adjust the base path for both files
        if len(slots) > 1:
            # Remove .zip extension to create base path
            base_output = output_file[:-4] if output_file.endswith('.zip') else output_file
        
        # Create progress dialog
        progress = QProgressDialog('Creating music pack...', 'Cancel', 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        # Prepare metadata - create TWO metadata objects
        mod_author = self.mod_author_input.text().strip() or "Unknown"
        mod_description = self.mod_description_input.toPlainText().strip() or "A custom music pack."
        game_description_en = self.game_description_input.toPlainText().strip() or "A custom music pack."
        
        # Build language-specific names (use English as fallback)
        game_names = {'en': game_name_en}
        game_names.update(self.name_lang_values)
        # Fill in missing languages with English
        for lang in ['it', 'gr', 'fr', 'sp']:
            if lang not in game_names:
                game_names[lang] = game_name_en
        
        # Build language-specific descriptions (use English as fallback)
        game_descriptions = {'en': game_description_en}
        game_descriptions.update(self.desc_lang_values)
        # Fill in missing languages with English
        for lang in ['it', 'gr', 'fr', 'sp']:
            if lang not in game_descriptions:
                game_descriptions[lang] = game_description_en
        
        # Progress callback
        def update_progress(current, total, message):
            if progress.wasCanceled():
                return
            progress.setValue(current)
            progress.setLabelText(message)
        
        # Export pack(s) for each slot
        exported_files = []
        try:
            for slot in slots:
                # Create slot-specific output filename
                if len(slots) == 1:
                    slot_output = output_file
                else:
                    slot_output = f"{base_output}-SL{slot}.zip"
                
                # Create metadata for this slot
                mod_metadata = MusicPackMetadata(mod_title, mod_author, mod_description, slot)
                game_metadata = MusicPackMetadata(game_name_en, mod_author, game_description_en, slot)
                
                # Update progress message
                if len(slots) > 1:
                    progress.setLabelText(f"Exporting Slot {slot}...")
                
                # Export the pack
                success = self.exporter.export_pack(
                    slot_output,
                    mod_metadata,
                    game_metadata,
                    self.track_assignments,
                    progress_callback=update_progress,
                    converter=getattr(self.parent_window, 'converter', None),
                    language_names=game_names,
                    language_descriptions=game_descriptions
                )
                
                if success:
                    exported_files.append(slot_output)
                else:
                    progress.close()
                    show_themed_message(self, QMessageBox.Critical, 'Error',
                                      f'Failed to create music pack for Slot {slot}. Check the log for details.')
                    return
            
            progress.close()
            
            # Show success message with all exported files
            if len(exported_files) == 1:
                message = f'Music pack created successfully!\n\n{exported_files[0]}'
            else:
                files_list = '\n'.join(exported_files)
                message = f'Music packs created successfully!\n\n{files_list}'
            
            show_themed_message(self, QMessageBox.Information, 'Success', message)
            # Don't close dialog - allow user to create more packs
            
        except Exception as e:
            logging.error(f"Error creating music pack: {e}", exc_info=True)
            show_themed_message(self, QMessageBox.Critical, 'Error',
                              f'Failed to create music pack:\n{str(e)}')
        finally:
            progress.close()

    def load_existing_pack(self):
        """Load a previously exported music pack and restore assignments"""
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            'Open Music Pack',
            '',
            'ZIP Files (*.zip);;All Files (*.*)'
        )

        if not zip_path:
            return

        data = self.exporter.load_pack(zip_path)
        if not data:
            show_themed_message(
                self,
                QMessageBox.Warning,
                'No Mapping Found',
                'This pack does not contain source mapping data, so assignments cannot be restored.'
            )
            return

        # Reset current assignments
        self.reset_assignments()

        # Restore metadata
        mod_meta = data.get('mod_metadata', {})
        game_meta = data.get('game_metadata', {})
        self.mod_title_input.setText(mod_meta.get('title', ''))
        self.mod_author_input.setText(mod_meta.get('author', ''))
        self.mod_description_input.setPlainText(mod_meta.get('description', ''))
        self.game_name_input.setText(game_meta.get('name', ''))
        self.game_description_input.setPlainText(game_meta.get('description', ''))

        # Restore language values
        self.name_lang_values = data.get('language_names', {}) or {}
        self.desc_lang_values = data.get('language_descriptions', {}) or {}
        self.update_lang_indicator(self.name_lang_indicator, self.name_lang_values)
        self.update_lang_indicator(self.desc_lang_indicator, self.desc_lang_values)

        # Restore slot selection
        slot_value = data.get('slot', 1)
        if slot_value == 0:
            self.slot0_radio.setChecked(True)
        elif slot_value == 1:
            self.slot1_radio.setChecked(True)
        elif slot_value == 2:
            self.slot2_radio.setChecked(True)
        else:
            self.slot1_radio.setChecked(True)

        # Build lookup for library files by basename
        library_by_basename = {}
        for path in self.library_files:
            base = os.path.basename(path).lower()
            library_by_basename.setdefault(base, []).append(path)

        # Restore assignments using stored mapping
        matched = 0
        missing = []
        for track in data.get('tracks', []):
            vanilla = track.get('vanilla_filename')
            source_path = track.get('source_path')
            source_base = (track.get('source_basename') or '').lower()

            chosen_path = None
            if source_path and os.path.exists(source_path):
                chosen_path = source_path
            elif source_base and source_base in library_by_basename:
                chosen_path = library_by_basename[source_base][0]

            if vanilla and chosen_path:
                self.assign_track(vanilla, chosen_path)
                matched += 1
            elif vanilla:
                missing.append((vanilla, track.get('source_basename', '?')))

        self.update_stats()

        # Show summary
        summary = f"Restored {matched} assignments."
        if missing:
            missing_list = '\n'.join([f"{v} ← {src}" for v, src in missing[:10]])
            if len(missing) > 10:
                missing_list += f"\n...and {len(missing) - 10} more"
            summary += f"\nCould not find matches for {len(missing)} tracks:\n{missing_list}"

        show_themed_message(
            self,
            QMessageBox.Information,
            'Music Pack Loaded',
            summary
        )
