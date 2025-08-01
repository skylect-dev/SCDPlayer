"""Kingdom Hearts Randomizer music export functionality"""
import os
import shutil
from typing import Dict, List, Set, Optional
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QListWidget, QFileDialog, QMessageBox, QGroupBox, QCheckBox, QScrollArea, QWidget
from PyQt5.QtCore import Qt
from ui.dialogs import apply_title_bar_theming


class KHRandoExporter:
    """Handle Kingdom Hearts Randomizer music export operations"""
    
    # KH Rando folder structure
    MUSIC_CATEGORIES = {
        'atlantica': 'Atlantica',
        'battle': 'Battle',
        'boss': 'Boss Battle', 
        'cutscene': 'Cutscene',
        'field': 'Field',
        'title': 'Title',
        'wild': 'Wild'
    }
    
    def __init__(self, parent=None):
        self.parent = parent
        self.kh_rando_path = None
        self.existing_files: Dict[str, Set[str]] = {}
        
    def is_valid_kh_rando_folder(self, path: str) -> bool:
        """Check if path contains valid KH Rando music folder structure"""
        if not os.path.exists(path):
            return False
            
        required_folders = set(folder.lower() for folder in self.MUSIC_CATEGORIES.keys())
        existing_folders = set()
        
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path) and item.lower() in required_folders:
                    existing_folders.add(item.lower())
        except (OSError, PermissionError):
            return False
            
        # Require at least 4 of the 7 folders to be present
        return len(existing_folders) >= 4
    
    def scan_existing_files(self, kh_rando_path: str) -> Dict[str, Set[str]]:
        """Scan existing files in KH Rando music folders"""
        existing_files = {}
        
        # Scan category folders
        for category in self.MUSIC_CATEGORIES.keys():
            actual_folder_name = self.find_actual_folder_name(kh_rando_path, category)
            category_path = os.path.join(kh_rando_path, actual_folder_name)
            files = set()
            
            if os.path.exists(category_path):
                try:
                    for file in os.listdir(category_path):
                        # Only SCD files are valid for KH Rando
                        if file.lower().endswith('.scd'):
                            files.add(file.lower())
                except (OSError, PermissionError):
                    pass
                    
            existing_files[category] = files
        
        # Also scan root folder for misplaced files (these won't load properly)
        root_files = set()
        if os.path.exists(kh_rando_path):
            try:
                for file in os.listdir(kh_rando_path):
                    file_path = os.path.join(kh_rando_path, file)
                    # Only check files (not directories) and only SCD files
                    if os.path.isfile(file_path) and file.lower().endswith('.scd'):
                        root_files.add(file.lower())
            except (OSError, PermissionError):
                pass
        
        existing_files['root'] = root_files
        
        return existing_files
    
    def find_actual_folder_name(self, kh_rando_path: str, category: str) -> str:
        """Find the actual folder name for a category (case-insensitive)"""
        if not os.path.exists(kh_rando_path):
            return category
            
        try:
            for item in os.listdir(kh_rando_path):
                item_path = os.path.join(kh_rando_path, item)
                if os.path.isdir(item_path) and item.lower() == category.lower():
                    return item
        except (OSError, PermissionError):
            pass
            
        # Return the standard name if not found
        return category
    
    def is_file_in_kh_rando(self, filename: str) -> List[str]:
        """Check which KH Rando categories contain this file (comparing base names without extensions)"""
        if not self.existing_files:
            return []
            
        # Get base name without extension for comparison
        base_name = os.path.splitext(os.path.basename(filename))[0].lower()
        found_in = []
        
        for category, files in self.existing_files.items():
            # Check if any file in this category has the same base name
            for kh_file in files:
                kh_base_name = os.path.splitext(kh_file)[0].lower()
                if base_name == kh_base_name:
                    found_in.append(category)
                    break  # Found in this category, no need to check other files
                
        return found_in

    def get_root_folder_files(self) -> List[str]:
        """Get list of files in the root KH Rando folder (these won't load properly)"""
        if not self.existing_files or 'root' not in self.existing_files:
            return []
        
        return list(self.existing_files['root'])

    def is_file_path_in_kh_rando(self, file_path: str) -> bool:
        """Check if a specific file path is within the KH Rando folder structure"""
        if not self.kh_rando_path or not file_path:
            return False
            
        try:
            # Normalize paths for comparison
            kh_rando_abs = os.path.abspath(self.kh_rando_path)
            file_abs = os.path.abspath(file_path)
            
            # Check if file is within KH Rando directory
            return file_abs.startswith(kh_rando_abs)
        except (OSError, ValueError):
            return False
    
    def export_file(self, source_path: str, category: str, kh_rando_path: str) -> bool:
        """Export a single file to KH Rando music folder (SCD files only)"""
        if not os.path.exists(source_path):
            return False
        
        # Check if file is SCD format
        file_ext = os.path.splitext(source_path)[1].lower()
        if file_ext != '.scd':
            # Only SCD files are supported by KH Rando
            return False
            
        # Find the actual folder name (case-insensitive)
        actual_folder_name = self.find_actual_folder_name(kh_rando_path, category)
        category_path = os.path.join(kh_rando_path, actual_folder_name)
        
        # Create category folder if it doesn't exist
        try:
            os.makedirs(category_path, exist_ok=True)
        except (OSError, PermissionError):
            return False
            
        filename = os.path.basename(source_path)
        dest_path = os.path.join(category_path, filename)
        
        try:
            shutil.copy2(source_path, dest_path)
            
            # Update existing files tracking
            if category not in self.existing_files:
                self.existing_files[category] = set()
            self.existing_files[category].add(filename.lower())
            
            return True
        except (OSError, PermissionError, shutil.Error):
            return False
    
    def set_kh_rando_path(self, path: str):
        """Set the KH Rando path and scan existing files"""
        self.kh_rando_path = path
        if path:
            self.existing_files = self.scan_existing_files(path)
        else:
            self.existing_files = {}
    
    def refresh_existing_files(self):
        """Refresh the existing files cache if KH Rando path is set"""
        if self.kh_rando_path:
            self.existing_files = self.scan_existing_files(self.kh_rando_path)


class KHRandoExportDialog(QDialog):
    """Dialog for selecting KH Rando export options"""
    
    def __init__(self, files_to_export: List[str], kh_rando_exporter: KHRandoExporter, parent=None):
        super().__init__(parent)
        self.files_to_export = files_to_export
        self.exporter = kh_rando_exporter
        self.file_categories = {}  # filename -> category mapping
        
        self.setWindowTitle("Export to KH Rando")
        self.setModal(True)
        self.resize(800, 500)  # Wider dialog
        
        self.setup_ui()
        apply_title_bar_theming(self)
        
    def setup_ui(self):
        """Setup the export dialog UI"""
        layout = QVBoxLayout()
        
        # Create main sections
        layout.addWidget(self.create_path_selection_group())
        layout.addWidget(self.create_file_assignment_group())
        layout.addLayout(self.create_dialog_buttons())
        
        self.setLayout(layout)
        
        # Use already configured KH Rando path if available
        if self.exporter.kh_rando_path:
            self.set_kh_rando_path(self.exporter.kh_rando_path)
    
    def create_path_selection_group(self):
        """Create the KH Rando path selection group"""
        path_group = QGroupBox("KH Rando Music Folder")
        path_layout = QVBoxLayout()
        
        self.path_label = QLabel("No KH Rando folder selected")
        path_layout.addWidget(self.path_label)
        
        path_btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_kh_rando_path)
        path_btn_layout.addWidget(self.browse_btn)
        
        path_btn_layout.addStretch()
        path_layout.addLayout(path_btn_layout)
        path_group.setLayout(path_layout)
        
        return path_group
    
    def create_file_assignment_group(self):
        """Create the file category assignment group"""
        files_group = QGroupBox("File Category Assignment")
        files_layout = QVBoxLayout()
        
        # Quick assignment buttons
        files_layout.addLayout(self.create_quick_assignment_buttons())
        
        # Separator line
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #404040; margin: 5px 0px;")
        files_layout.addWidget(separator)
        
        # Create scrollable area for file assignments
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(400)  # Limit height to keep dialog manageable
        
        # Create widget to hold file assignments
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Individual file assignments
        for file_path in self.files_to_export:
            scroll_layout.addLayout(self.create_file_assignment_row(file_path))
        
        scroll_layout.addStretch()  # Add stretch to push items to top
        scroll_area.setWidget(scroll_widget)
        files_layout.addWidget(scroll_area)
        
        files_group.setLayout(files_layout)
        return files_group
    
    def create_quick_assignment_buttons(self):
        """Create the quick assignment button row"""
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Assign all files to:"))
        quick_layout.addStretch()
        
        for cat_key, cat_name in self.exporter.MUSIC_CATEGORIES.items():
            btn = QPushButton(cat_name)
            btn.clicked.connect(lambda checked, c=cat_key: self.assign_all_category(c))
            btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 8px;
                    font-size: 11px;
                    min-height: 20px;
                    border-radius: 4px;
                }
            """)
            quick_layout.addWidget(btn)
        
        return quick_layout
    
    def create_file_assignment_row(self, file_path):
        """Create assignment row for a single file"""
        filename = os.path.basename(file_path)
        file_layout = QVBoxLayout()
        
        # File info row
        info_layout = QHBoxLayout()
        
        # Filename label (truncated if too long)
        name_label = QLabel(filename if len(filename) <= 60 else filename[:57] + "...")
        name_label.setToolTip(filename)
        name_label.setStyleSheet("font-weight: bold; color: white;")
        info_layout.addWidget(name_label)
        
        # Check if file already exists in KH Rando
        existing_cats = self.exporter.is_file_in_kh_rando(filename)
        if existing_cats:
            status_text = f"(Already in: {', '.join(existing_cats)})"
            status_label = QLabel(status_text)
            status_label.setStyleSheet("color: orange;")
            info_layout.addWidget(status_label)
        
        info_layout.addStretch()
        file_layout.addLayout(info_layout)
        
        # Category dropdown row
        dropdown_layout = QHBoxLayout()
        dropdown_layout.addWidget(QLabel("Category:"))
        
        # Create dropdown for this file
        category_combo = QComboBox()
        category_combo.addItem("Select category...", "")
        for cat_key, cat_name in self.exporter.MUSIC_CATEGORIES.items():
            category_combo.addItem(cat_name, cat_key)
        
        category_combo.currentTextChanged.connect(
            lambda text, f=filename, combo=category_combo: self.set_file_category_dropdown(f, combo)
        )
        
        dropdown_layout.addWidget(category_combo)
        dropdown_layout.addStretch()
        
        file_layout.addLayout(dropdown_layout)
        file_layout.addSpacing(10)
        
        self.file_categories[filename] = category_combo
        return file_layout
    
    def create_dialog_buttons(self):
        """Create the dialog button layout"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.export_btn = QPushButton("Export Selected")
        self.export_btn.clicked.connect(self.export_files)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        return button_layout
        
    def set_file_category_dropdown(self, filename: str, combo: QComboBox):
        """Handle category selection from dropdown"""
        self.update_export_button()
    
    def assign_all_category(self, category: str):
        """Assign category to all files using dropdowns"""
        for filename, combo in self.file_categories.items():
            # Find the index of the category in the combo box
            for i in range(combo.count()):
                if combo.itemData(i) == category:
                    combo.setCurrentIndex(i)
                    break
        self.update_export_button()
    
    def update_export_button(self):
        """Update export button state based on selections"""
        has_selection = False
        for combo in self.file_categories.values():
            if combo.currentData():  # Has valid category selected
                has_selection = True
                break
        self.export_btn.setEnabled(has_selection)
    
    def browse_kh_rando_path(self):
        """Browse for KH Rando music folder"""
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select KH Rando Music Folder")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        # Set default directory if it exists
        default_path = "D:/KHRandoReMix/Seed Gen/music"
        if os.path.exists("D:/KHRandoReMix"):
            dialog.setDirectory(default_path)
        
        # Apply title bar theming
        apply_title_bar_theming(dialog)
        
        if dialog.exec_() == QFileDialog.Accepted:
            selected = dialog.selectedFiles()
            if selected:
                self.set_kh_rando_path(selected[0])

    def set_kh_rando_path(self, path: str):
        """Set and validate KH Rando path"""
        if self.exporter.is_valid_kh_rando_folder(path):
            self.exporter.set_kh_rando_path(path)
            self.path_label.setText(f"Selected: {path}")
            self.path_label.setStyleSheet("color: green;")
            self.export_btn.setEnabled(True)
            
            # Update existing file indicators
            self.update_existing_file_indicators()
        else:
            QMessageBox.warning(
                self, 
                "Invalid Folder", 
                "The selected folder does not appear to be a valid KH Rando music folder.\n\n"
                "Expected subfolders (case-insensitive): atlantica, battle, boss, cutscene, field, title, wild\n\n"
                "At least 4 of these folders must be present."
            )

    def update_existing_file_indicators(self):
        """Update UI to show which files already exist in KH Rando"""
        # This would require rebuilding the UI or updating existing widgets
        # For now, the indicators are set during initial UI creation
        pass
    

    
    def export_files(self):
        """Export selected files with their assigned categories"""
        if not self.exporter.kh_rando_path:
            QMessageBox.warning(self, "No Path", "Please select a KH Rando music folder first.")
            return
        
        exported_count = 0
        skipped_count = 0
        error_count = 0
        
        for file_path in self.files_to_export:
            filename = os.path.basename(file_path)
            combo = self.file_categories[filename]
            
            # Get the selected category from dropdown
            category = combo.currentData()
            
            if not category:
                skipped_count += 1
                continue
                
            if self.exporter.export_file(file_path, category, self.exporter.kh_rando_path):
                exported_count += 1
            else:
                error_count += 1
        
        # Show results
        msg = f"Export completed:\n"
        msg += f"• Exported: {exported_count} files\n"
        if skipped_count > 0:
            msg += f"• Skipped (no category): {skipped_count} files\n"
        if error_count > 0:
            msg += f"• Errors: {error_count} files\n"
        
        QMessageBox.information(self, "Export Results", msg)
        
        if exported_count > 0:
            self.accept()
        elif error_count == 0:
            self.reject()
