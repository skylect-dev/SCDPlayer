import logging
import os
import tempfile
from pathlib import Path

from PyQt5.QtCore import QTimer, Qt, QMimeData, QUrl
from PyQt5.QtGui import QColor, QCursor, QDrag, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs import show_themed_file_dialog, show_themed_message, apply_title_bar_theming
from utils.helpers import format_time, send_to_recycle_bin
from core.library import AudioLibrary


class LibraryController:
    """Encapsulate library, KH Rando, and context menu logic for SCDToolkit."""

    def __init__(self, window):
        self.window = window
        self._updating_selection = False
        self.kh_rando_categories = {}
        self.kh_rando_category_states = {}
        self._files_by_folder_cache = {}
        self._folder_expanded_states = {}
        self._drag_hover_item = None
        self.library = None

    # UI construction
    def create_library_panel(self):
        """Build the library panel UI and wire signals."""
        w = self.window

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
        self.remove_folder_btn = remove_folder_btn
        w.remove_folder_btn = remove_folder_btn
        folder_controls.addWidget(remove_folder_btn)

        rescan_btn = QPushButton('Rescan')
        rescan_btn.clicked.connect(self.rescan_library)
        folder_controls.addWidget(rescan_btn)
        header_layout.addLayout(folder_controls)

        # Folder list
        header_layout.addWidget(QLabel('Scan Folders:'))
        self.folder_list = QListWidget()
        w.folder_list = self.folder_list
        self.folder_list.setVerticalScrollMode(self.folder_list.ScrollPerPixel)
        self.folder_list.verticalScrollBar().setSingleStep(8)
        self.folder_list.setMaximumHeight(100)
        self.folder_list.itemSelectionChanged.connect(self.on_folder_selection_changed)
        self.folder_list.setStyleSheet("QListWidget::item:selected{outline:0;} QListWidget::item:focus{outline:0;}")
        for folder in w.config.library_folders:
            self.folder_list.addItem(folder)
        self.remove_folder_btn.setEnabled(False)
        header_layout.addWidget(self.folder_list)

        # Scan subdirs toggle
        self.subdirs_checkbox = QCheckBox('Scan subdirectories')
        w.subdirs_checkbox = self.subdirs_checkbox
        self.subdirs_checkbox.stateChanged.connect(self.toggle_subdirs)
        self.subdirs_checkbox.setChecked(w.config.scan_subdirs)
        header_layout.addWidget(self.subdirs_checkbox)

        # KH Rando folder controls
        kh_rando_layout = QHBoxLayout()
        kh_rando_layout.addWidget(QLabel('KH Rando Folder:'))

        self.kh_rando_path_label = QLabel('Not selected')
        self.kh_rando_path_label.setStyleSheet("color: gray; font-style: italic;")
        self.kh_rando_path_label.setMinimumWidth(250)
        kh_rando_layout.addWidget(self.kh_rando_path_label)

        self.edit_musiclist_btn = QPushButton('Edit Music List (J)')
        self.edit_musiclist_btn.clicked.connect(w.show_musiclist_editor)
        self.edit_musiclist_btn.setToolTip('Edit musiclist.json for KH Randomizer')
        kh_rando_layout.addWidget(self.edit_musiclist_btn)

        select_kh_rando_btn = QPushButton('Select KH Rando Folder')
        select_kh_rando_btn.clicked.connect(self.select_kh_rando_folder)
        self.select_kh_rando_btn = select_kh_rando_btn
        kh_rando_layout.addWidget(select_kh_rando_btn)

        self.open_kh_rando_btn = QPushButton('Open Folder')
        self.open_kh_rando_btn.clicked.connect(self.open_kh_rando_folder)
        self.open_kh_rando_btn.setEnabled(False)
        self.open_kh_rando_btn.setToolTip('Open the KH Rando folder in file explorer')
        kh_rando_layout.addWidget(self.open_kh_rando_btn)

        kh_rando_layout.addStretch()
        header_layout.addLayout(kh_rando_layout)

        library_header.setLayout(header_layout)
        library_layout.addWidget(library_header)

        # Create vertical splitter between header and file libraries
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setChildrenCollapsible(False)
        library_layout.removeWidget(library_header)
        main_splitter.addWidget(library_header)

        files_widget = QWidget()
        files_layout = QHBoxLayout()
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(5)

        files_splitter = QSplitter(Qt.Horizontal)
        files_splitter.setChildrenCollapsible(False)

        # Regular files list
        regular_files_widget = QWidget()
        regular_files_layout = QVBoxLayout()
        regular_files_layout.setContentsMargins(0, 0, 0, 0)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_container = QHBoxLayout()
        search_container.setContentsMargins(0, 0, 0, 0)
        search_container.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files... (filename or folder)")
        self.search_input.textChanged.connect(self.filter_library_files)
        search_container.addWidget(self.search_input)
        w.search_input = self.search_input

        self.clear_search_btn = QPushButton("×")
        self.clear_search_btn.clicked.connect(self.clear_search)
        self.clear_search_btn.setMaximumWidth(25)
        self.clear_search_btn.setMaximumHeight(25)
        self.clear_search_btn.setToolTip("Clear search")
        self.clear_search_btn.setStyleSheet(
            """
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
        """
        )
        search_container.addWidget(self.clear_search_btn)

        search_layout.addWidget(QLabel("Search:"))
        search_layout.addLayout(search_container)
        regular_files_layout.addLayout(search_layout)

        org_layout = QHBoxLayout()
        org_layout.setContentsMargins(0, 0, 0, 0)

        self.organize_by_folder_cb = QCheckBox("Group by folder")
        self.organize_by_folder_cb.stateChanged.connect(self.toggle_folder_organization)
        self.organize_by_folder_cb.setToolTip("Organize files by their originating folder")
        self.organize_by_folder_cb.setChecked(True)
        org_layout.addWidget(self.organize_by_folder_cb)

        org_layout.addStretch()
        regular_files_layout.addLayout(org_layout)

        regular_files_layout.addWidget(QLabel('Audio Files:'))
        self.file_list = QListWidget()
        w.file_list = self.file_list
        self.file_list.setVerticalScrollMode(self.file_list.ScrollPerPixel)
        self.file_list.verticalScrollBar().setSingleStep(8)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.itemDoubleClicked.connect(self.load_from_library)
        self.file_list.itemClicked.connect(self.on_library_item_clicked)
        self.file_list.itemSelectionChanged.connect(self.on_library_selection_changed)
        self.file_list.setStyleSheet(
            "QListWidget::item:selected{outline:0;} QListWidget::item:focus{outline:0;} QListWidget{border:1px solid #333;}"
        )
        self.file_list.setDragEnabled(True)
        self.file_list.setDragDropMode(QListWidget.DragOnly)
        self.file_list.startDrag = lambda supportedActions: self.start_file_drag(self.file_list, supportedActions)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        regular_files_layout.addWidget(self.file_list)

        regular_files_widget.setLayout(regular_files_layout)
        files_splitter.addWidget(regular_files_widget)

        # KH Rando files list
        kh_rando_widget = QWidget()
        kh_rando_layout = QVBoxLayout()
        kh_rando_layout.setContentsMargins(0, 0, 0, 0)

        kh_header_layout = QHBoxLayout()
        kh_header_layout.addWidget(QLabel('KH Randomizer Files:'))
        kh_header_layout.addStretch()

        add_kh_folder_btn = QPushButton('Create New Folder')
        add_kh_folder_btn.clicked.connect(self.add_kh_rando_folder)
        add_kh_folder_btn.setMaximumWidth(30)
        add_kh_folder_btn.setMaximumHeight(25)
        add_kh_folder_btn.setToolTip('Add new folder to KH Randomizer music directory')
        kh_header_layout.addWidget(add_kh_folder_btn)
        kh_rando_layout.addLayout(kh_header_layout)

        self.kh_rando_file_list = QListWidget()
        self.kh_rando_file_list.setVerticalScrollMode(self.kh_rando_file_list.ScrollPerPixel)
        self.kh_rando_file_list.verticalScrollBar().setSingleStep(8)
        self.kh_rando_file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.kh_rando_file_list.itemDoubleClicked.connect(self.load_from_library)
        self.kh_rando_file_list.itemClicked.connect(self.on_kh_rando_item_clicked)
        self.kh_rando_file_list.itemSelectionChanged.connect(self.on_kh_rando_selection_changed)
        self.kh_rando_file_list.setStyleSheet(
            "QListWidget::item:selected{outline:0;} QListWidget::item:focus{outline:0;} QListWidget{border:1px solid #333;}"
        )
        self.kh_rando_file_list.setAcceptDrops(True)
        self.kh_rando_file_list.setDragDropMode(QListWidget.DropOnly)
        self.kh_rando_file_list.dragEnterEvent = lambda event: self.kh_rando_drag_enter_event(event)
        self.kh_rando_file_list.dragMoveEvent = lambda event: self.kh_rando_drag_move_event(event)
        self.kh_rando_file_list.dragLeaveEvent = lambda event: self.kh_rando_drag_leave_event(event)
        self.kh_rando_file_list.dropEvent = lambda event: self.kh_rando_drop_event(event)
        self.kh_rando_file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.kh_rando_file_list.customContextMenuRequested.connect(self.show_kh_rando_context_menu)
        self.kh_rando_categories = {}
        self.kh_rando_category_states = {}
        kh_rando_layout.addWidget(self.kh_rando_file_list)

        kh_rando_widget.setLayout(kh_rando_layout)
        files_splitter.addWidget(kh_rando_widget)

        files_splitter.setSizes([300, 300])
        files_layout.addWidget(files_splitter)
        files_widget.setLayout(files_layout)
        main_splitter.addWidget(files_widget)
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
        self.delete_selected_btn.setEnabled(False)
        library_buttons_layout.addWidget(self.delete_selected_btn)

        self.open_file_location_btn = QPushButton('Open File Location (Ctrl+L)')
        self.open_file_location_btn.clicked.connect(self.open_file_location)
        self.open_file_location_btn.setToolTip(
            'Open the folder containing the selected file or currently playing file in File Explorer (Ctrl+L)'
        )
        self.open_file_location_btn.setEnabled(False)
        library_buttons_layout.addWidget(self.open_file_location_btn)
        library_layout.addLayout(library_buttons_layout)

        # Conversion buttons
        convert_buttons_layout = QHBoxLayout()
        self.convert_to_wav_btn = QPushButton('Convert Selected to WAV (W)')
        self.convert_to_wav_btn.clicked.connect(self.convert_selected_to_wav)
        self.convert_to_wav_btn.setEnabled(False)
        self.convert_to_wav_btn.setToolTip('Convert selected library files to WAV format')
        convert_buttons_layout.addWidget(self.convert_to_wav_btn)

        self.convert_to_scd_btn = QPushButton('Convert Selected to SCD (S)')
        self.convert_to_scd_btn.clicked.connect(self.convert_selected_to_scd)
        self.convert_to_scd_btn.setEnabled(False)
        self.convert_to_scd_btn.setToolTip('Convert selected library files to SCD format')
        convert_buttons_layout.addWidget(self.convert_to_scd_btn)

        self.open_loop_editor_btn = QPushButton('Open Loop Editor (L)')
        self.open_loop_editor_btn.clicked.connect(w.open_loop_editor)
        self.open_loop_editor_btn.setEnabled(False)
        self.open_loop_editor_btn.setToolTip('Edit loop points for selected SCD or WAV file with professional waveform editor')
        convert_buttons_layout.addWidget(self.open_loop_editor_btn)
        library_layout.addLayout(convert_buttons_layout)

        # Music Pack Creator button
        music_pack_layout = QHBoxLayout()
        self.music_pack_creator_btn = QPushButton('Create Music Pack (Kingdom Hearts II - Re:Fined)')
        self.music_pack_creator_btn.clicked.connect(w.open_music_pack_creator)
        self.music_pack_creator_btn.setToolTip('Create a music pack mod for Kingdom Hearts II - Re:Fined')
        self.music_pack_creator_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1a4d2e;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #2d6a4f;
            }
        """
        )
        music_pack_layout.addWidget(self.music_pack_creator_btn)
        library_layout.addLayout(music_pack_layout)

        # Library model
        self.library = AudioLibrary(self.file_list, w.kh_rando_exporter, self.kh_rando_file_list, self.kh_rando_categories)
        w.library = self.library

        if w.config.kh_rando_folder:
            self.set_kh_rando_folder(w.config.kh_rando_folder)
            w.kh_rando_exporter.set_kh_rando_path(w.config.kh_rando_folder)
            self._update_kh_rando_categories()

        QTimer.singleShot(10, self.perform_initial_scan)
        QTimer.singleShot(50, self._update_kh_rando_section_counts)

        library_panel.setLayout(library_layout)
        return library_panel

    # Selection handling
    def on_kh_rando_selection_changed(self):
        if self._updating_selection:
            return

        selected_items = []
        if hasattr(self, 'kh_rando_file_list'):
            selected_items = self.kh_rando_file_list.selectedItems()

        file_items = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
                file_items.append(item)

        if file_items:
            self._updating_selection = True
            self.file_list.clearSelection()
            self._updating_selection = False

        self.on_library_selection_changed_common(file_items)

    def on_folder_selection_changed(self):
        has_selection = self.folder_list.currentItem() is not None
        self.remove_folder_btn.setEnabled(has_selection)

    # Folder management
    def add_library_folder(self):
        folder = QFileDialog.getExistingDirectory(self.window, 'Select Folder')
        if folder and folder not in self.window.config.library_folders:
            self.window.config.library_folders.append(folder)
            self.folder_list.addItem(folder)
            self.window.config.save_settings()
            if hasattr(self.window, 'file_watcher') and self.window.file_watcher:
                self.window.file_watcher.scan_initial_files([folder], self.window.config.scan_subdirs)
                self.window.file_watcher.add_watch_paths([folder], self.window.config.scan_subdirs)
            self.rescan_library()

    def remove_library_folder(self):
        current_row = self.folder_list.currentRow()
        if current_row >= 0:
            removed_folder = self.window.config.library_folders[current_row]
            self.window.config.library_folders.pop(current_row)
            self.folder_list.takeItem(current_row)
            self.window.config.save_settings()
            if hasattr(self.window, 'file_watcher') and self.window.file_watcher:
                self.window.file_watcher.remove_watch_paths([removed_folder])
            self.rescan_library()

    def toggle_subdirs(self, state):
        self.window.config.scan_subdirs = bool(state)
        self.window.config.save_settings()
        if self.library:
            self.rescan_library()

    # KH Rando folder selection
    def select_kh_rando_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self.window,
            'Select KH Rando Music Folder',
            self.window.config.kh_rando_folder if self.window.config.kh_rando_folder else ""
        )
        if folder:
            self.set_kh_rando_folder(folder)

    def set_kh_rando_folder(self, folder_path):
        exporter = self.window.kh_rando_exporter
        if exporter.is_valid_kh_rando_folder(folder_path):
            self.window.config.kh_rando_folder = folder_path
            self.window.config.save_settings()
            exporter.set_kh_rando_path(folder_path)
            self._update_kh_rando_categories()

            parent_dir = os.path.dirname(folder_path)
            musiclist_path = os.path.join(parent_dir, "musiclist.json")
            has_musiclist = os.path.exists(musiclist_path)
            folder_name = os.path.basename(folder_path)
            status_text = f"✓ {folder_name}"
            status_text += "  ✓ musiclist.json" if has_musiclist else "  ⚠ musiclist.json missing"
            self.kh_rando_path_label.setText(status_text)
            self.kh_rando_path_label.setStyleSheet("color: green;")
            self.open_kh_rando_btn.setEnabled(True)
            if self.library:
                self.rescan_library()
        else:
            show_themed_message(
                self.window, QMessageBox.Warning,
                "Invalid KH Rando Folder",
                "The selected folder does not appear to be a valid KH Rando music folder.\n\n"
                "Expected subfolders (case-insensitive): atlantica, battle, boss, cutscene, field, title, wild\n\n"
                "At least 4 of these folders must be present."
            )

    def open_kh_rando_folder(self):
        if not self.window.config.kh_rando_folder or not os.path.exists(self.window.config.kh_rando_folder):
            show_themed_message(
                self.window, QMessageBox.Warning,
                "No KH Rando Folder",
                "Please select a valid KH Rando folder first."
            )
            return
        try:
            os.startfile(self.window.config.kh_rando_folder)
        except Exception as e:
            show_themed_message(
                self.window, QMessageBox.Warning,
                "Error Opening Folder",
                f"Could not open the KH Rando folder:\n{str(e)}"
            )

    # Library scan and filtering
    def rescan_library(self):
        if not self.library:
            return

        if hasattr(self.window, 'scan_overlay'):
            self.window.scan_overlay.show_scanning("Scanning library folders...")

        current_search = self.search_input.text() if hasattr(self, 'search_input') else ""
        organize_by_folder = self.organize_by_folder_cb.isChecked() if hasattr(self, 'organize_by_folder_cb') else False
        if current_search:
            self.search_input.clear()

        if hasattr(self.window, 'scan_overlay'):
            def on_scan_progress(current, total, filename):
                self.window.scan_overlay.update_progress(current, total, filename)
                QApplication.processEvents()
            self.library.set_progress_callback(on_scan_progress)

        try:
            self.library.scan_folders(self.window.config.library_folders, self.window.config.scan_subdirs, self.window.config.kh_rando_folder)
            self._populate_kh_rando_list()
            self._update_kh_rando_section_counts()
            self.folder_list.clear()
            for folder in self.window.config.library_folders:
                self.folder_list.addItem(folder)
            self.subdirs_checkbox.setChecked(self.window.config.scan_subdirs)
            if organize_by_folder:
                if hasattr(self, '_files_by_folder_cache'):
                    self._files_by_folder_cache.clear()
                self._organize_files_by_folder()
            if current_search:
                self.search_input.setText(current_search)
                self.filter_library_files()
        finally:
            self.library.set_progress_callback(None)
            if hasattr(self.window, 'scan_overlay'):
                self.window.scan_overlay.hide_scanning()

    def filter_library_files(self):
        search_text = self.search_input.text().lower()
        if not search_text:
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item.setHidden(False)
            return

        is_folder_mode = self.organize_by_folder_cb.isChecked()
        if is_folder_mode:
            current_folder = None
            folder_has_matches = False
            folder_header_item = None
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                if file_path and file_path.startswith("FOLDER_HEADER:"):
                    if folder_header_item is not None:
                        folder_header_item.setHidden(not folder_has_matches)
                    folder_header_item = item
                    folder_has_matches = False
                    current_folder = file_path.replace("FOLDER_HEADER:", "")
                else:
                    item_text = item.text().lower()
                    folder_path = os.path.dirname(file_path).lower() if file_path else ""
                    matches = (
                        search_text in item_text
                        or search_text in folder_path
                        or search_text in os.path.basename(folder_path)
                        or (current_folder and search_text in current_folder.lower())
                    )
                    item.setHidden(not matches)
                    if matches:
                        folder_has_matches = True
            if folder_header_item is not None:
                folder_header_item.setHidden(not folder_has_matches)
        else:
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                item_text = item.text().lower()
                folder_path = os.path.dirname(file_path).lower() if file_path else ""
                matches = (
                    search_text in item_text
                    or search_text in folder_path
                    or search_text in os.path.basename(folder_path)
                )
                item.setHidden(not matches)

    def clear_search(self):
        self.search_input.clear()
        self.filter_library_files()

    def toggle_folder_organization(self):
        organize_by_folder = self.organize_by_folder_cb.isChecked()
        if organize_by_folder:
            self._files_by_folder_cache.clear()
            self._organize_files_by_folder()
        else:
            self._folder_expanded_states.clear()
            self.rescan_library()

    def _get_expanded_folder_items(self):
        return [folder for folder, expanded in self._folder_expanded_states.items() if expanded]

    def _restore_expanded_folder_items(self, expanded_folders):
        for folder in list(self._folder_expanded_states.keys()):
            self._folder_expanded_states[folder] = folder in expanded_folders

    def _add_file_to_folder_cache(self, file_path: str, display_text: str, color):
        folder = os.path.dirname(file_path)
        folder_name = os.path.basename(folder) if folder and folder != "." else "Files (No Folder)"
        if folder_name not in self._files_by_folder_cache:
            self._files_by_folder_cache[folder_name] = []
        self._files_by_folder_cache[folder_name].append((display_text, file_path, color))

    def _remove_file_from_folder_cache(self, file_path: str):
        for folder_name in list(self._files_by_folder_cache.keys()):
            self._files_by_folder_cache[folder_name] = [
                (text, fpath, color) for text, fpath, color in self._files_by_folder_cache[folder_name]
                if fpath != file_path
            ]
            if not self._files_by_folder_cache[folder_name]:
                del self._files_by_folder_cache[folder_name]

    def _organize_files_by_folder(self):
        if not self.library:
            return

        current_search = self.search_input.text()
        if current_search:
            self.search_input.clear()
            self.filter_library_files()

        files_by_folder = {}
        use_cache = bool(self._files_by_folder_cache)
        if use_cache:
            files_by_folder = self._files_by_folder_cache.copy()
        else:
            kh_rando_path_obj = None
            if self.window.config.kh_rando_folder:
                try:
                    kh_rando_path_obj = Path(self.window.config.kh_rando_folder).resolve()
                except Exception:
                    kh_rando_path_obj = None
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                if file_path and not file_path.startswith("FOLDER_HEADER"):
                    if kh_rando_path_obj:
                        try:
                            if Path(file_path).resolve().is_relative_to(kh_rando_path_obj):
                                continue
                        except Exception:
                            pass
                    folder = os.path.dirname(file_path)
                    folder_name = os.path.basename(folder) if folder and folder != "." else "Files (No Folder)"
                    files_by_folder.setdefault(folder_name, []).append((item.text(), file_path, item.foreground()))
            self._files_by_folder_cache = files_by_folder

        self.file_list.clear()
        if not self._folder_expanded_states:
            self._folder_expanded_states = {}

        for folder_name in sorted(files_by_folder.keys()):
            if folder_name not in self._folder_expanded_states:
                self._folder_expanded_states[folder_name] = True
            is_expanded = self._folder_expanded_states[folder_name]
            arrow = "▼" if is_expanded else "▶"
            file_count = len(files_by_folder[folder_name])
            header_item = QListWidgetItem(f"{arrow} 📁 {folder_name} ({file_count})")
            header_item.setData(Qt.UserRole, f"FOLDER_HEADER:{folder_name}")
            header_item.setForeground(QColor('lightblue'))
            header_item.setFlags(header_item.flags() | Qt.ItemIsSelectable)
            self.file_list.addItem(header_item)

            if is_expanded:
                sorted_files = sorted(files_by_folder[folder_name], key=lambda x: os.path.basename(x[1]).lower())
                for file_text, file_path, file_color in sorted_files:
                    clean_text = file_text.lstrip()
                    file_item = QListWidgetItem(f"    {clean_text}")
                    file_item.setData(Qt.UserRole, file_path)
                    if file_color:
                        file_item.setForeground(file_color)
                    self.file_list.addItem(file_item)

        if current_search:
            self.search_input.setText(current_search)
            self.filter_library_files()
        if getattr(self.window, 'current_file', None):
            self.update_library_selection(self.window.current_file)

    # Item click handling
    def on_kh_rando_item_clicked(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and file_path.startswith("KH_CATEGORY_HEADER:"):
            category_key = file_path.replace("KH_CATEGORY_HEADER:", "")
            self._toggle_kh_category_expansion(category_key)
            return
        if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
            self._updating_selection = True
            self.file_list.clearSelection()
            self._updating_selection = False

    def on_library_item_clicked(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and file_path.startswith("FOLDER_HEADER:"):
            folder_name = file_path.replace("FOLDER_HEADER:", "")
            cursor_pos = self.file_list.mapFromGlobal(QCursor.pos())
            item_rect = self.file_list.visualItemRect(item)
            if cursor_pos.x() - item_rect.x() <= 20:
                self._toggle_folder_expansion(folder_name)
            else:
                self._select_files_in_folder(folder_name)

    def load_from_library(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and file_path.startswith("FOLDER_HEADER:"):
            return
        if file_path and file_path != "FOLDER_HEADER":
            self.window.load_file_path(file_path, auto_play=True)

    # KH Rando category helpers
    def _update_kh_rando_categories(self):
        exporter = getattr(self.window, 'kh_rando_exporter', None)
        if exporter:
            categories = exporter.get_categories()
            self.kh_rando_categories = categories.copy()
            for category_key in categories.keys():
                if category_key not in self.kh_rando_category_states:
                    self.kh_rando_category_states[category_key] = True
            if self.library:
                self.library.kh_rando_categories = self.kh_rando_categories

    def _update_kh_rando_section_counts(self):
        if hasattr(self, 'kh_rando_file_list'):
            self._populate_kh_rando_list()
            QApplication.processEvents()

    def _refresh_duplicate_status(self):
        exporter = getattr(self.window, 'kh_rando_exporter', None)
        if not exporter:
            return
        exporter.refresh_existing_files()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if not item:
                continue
            file_path = item.data(Qt.UserRole)
            if not file_path or file_path.startswith("FOLDER_HEADER:"):
                continue
            filename = os.path.basename(file_path)
            kh_categories = exporter.is_file_in_kh_rando(filename)
            kh_status = ""
            if kh_categories:
                if kh_categories == ['root']:
                    kh_status = " [KH: root folder - misplaced]"
                else:
                    display_categories = [cat for cat in kh_categories if cat != 'root']
                    if display_categories:
                        kh_status = f" [KH: {', '.join(display_categories)} - duplicate]"
            try:
                size = os.path.getsize(file_path)
                from utils.helpers import format_file_size
                size_str = format_file_size(size)
            except Exception:
                size_str = "? MB"
            display_text = f"{filename} ({size_str}){kh_status}"
            current_text = item.text()
            if current_text.startswith("    "):
                display_text = f"    {display_text}"
            item.setText(display_text)
            item.setForeground(QColor('orange') if kh_status else QColor('white'))

    def _select_files_in_folder(self, folder_name):
        self.file_list.clearSelection()
        found_folder = False
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path == f"FOLDER_HEADER:{folder_name}":
                found_folder = True
                continue
            elif found_folder and file_path and not file_path.startswith("FOLDER_HEADER"):
                item.setSelected(True)
            elif found_folder and file_path and file_path.startswith("FOLDER_HEADER"):
                break

    def _toggle_kh_category_expansion(self, category_key):
        if category_key not in self.kh_rando_category_states:
            return
        current_state = self.kh_rando_category_states[category_key]
        self.kh_rando_category_states[category_key] = not current_state
        self._populate_kh_rando_list()
        if getattr(self.window, 'current_file', None):
            self.update_library_selection(self.window.current_file)

    def add_kh_rando_folder(self):
        kh_rando_folder = self.window.config.kh_rando_folder
        if not kh_rando_folder or not os.path.exists(kh_rando_folder):
            QMessageBox.warning(
                self.window,
                "No KH Rando Directory",
                "KH Randomizer music directory not found. Please set it in the settings first."
            )
            return
        folder_name, ok = QInputDialog.getText(
            self.window,
            "Add New Folder",
            "Enter the name of the new folder:",
            QLineEdit.Normal,
            ""
        )
        if ok and folder_name:
            folder_name = folder_name.strip()
            if not folder_name:
                return
            new_folder_path = os.path.join(kh_rando_folder, folder_name)
            if os.path.exists(new_folder_path):
                QMessageBox.warning(
                    self.window,
                    "Folder Exists",
                    f"The folder '{folder_name}' already exists."
                )
                return
            try:
                os.makedirs(new_folder_path)
                logging.info(f"Created new KH Rando folder: {new_folder_path}")
                if self.library:
                    self.library.scan_folders(
                        self.window.config.library_folders,
                        self.window.config.scan_subdirs,
                        self.window.config.kh_rando_folder,
                    )
                    self._update_kh_rando_categories()
                    self._populate_kh_rando_list()
                QMessageBox.information(
                    self.window,
                    "Folder Created",
                    f"Successfully created folder '{folder_name}' in the KH Randomizer music directory.\n\nYou can now add files to this folder."
                )
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Error",
                    f"Failed to create folder:\n{e}"
                )
                logging.error(f"Failed to create KH Rando folder: {e}")

    def _populate_kh_rando_list(self):
        if not hasattr(self, 'kh_rando_file_list') or not self.library:
            return
        selected_paths = []
        for item in self.kh_rando_file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path and not path.startswith("KH_CATEGORY_HEADER:"):
                selected_paths.append(path)
        self.kh_rando_file_list.clear()
        files_by_category = getattr(self.library, 'kh_rando_files_by_category', {}) or {}
        for category_key, category_name in self.kh_rando_categories.items():
            is_expanded = self.kh_rando_category_states.get(category_key, True)
            category_files = files_by_category.get(category_key, [])
            file_count = len(category_files)
            arrow = "▼" if is_expanded else "▶"
            header_item = QListWidgetItem(f"{arrow} 📁 {category_name} ({file_count})")
            header_item.setData(Qt.UserRole, f"KH_CATEGORY_HEADER:{category_key}")
            header_item.setForeground(QColor('lightblue'))
            header_item.setFlags(header_item.flags() | Qt.ItemIsSelectable)
            self.kh_rando_file_list.addItem(header_item)
            if is_expanded and category_files:
                for file_path, display_name in sorted(category_files):
                    file_item = QListWidgetItem(f"    {display_name}")
                    file_item.setData(Qt.UserRole, file_path)
                    self.kh_rando_file_list.addItem(file_item)
        if selected_paths:
            for i in range(self.kh_rando_file_list.count()):
                item = self.kh_rando_file_list.item(i)
                if item.data(Qt.UserRole) in selected_paths:
                    item.setSelected(True)
        if getattr(self.window, 'current_file', None):
            self.update_library_selection(self.window.current_file)

    def _toggle_folder_expansion(self, folder_name):
        current_state = self._folder_expanded_states.get(folder_name, True)
        self._folder_expanded_states[folder_name] = not current_state
        new_state = not current_state
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
            return
        arrow = "▼" if new_state else "▶"
        current_text = folder_header_item.text()
        if "(" in current_text and ")" in current_text:
            file_count_part = current_text[current_text.rfind("("):]
            folder_header_item.setText(f"{arrow} 📁 {folder_name} {file_count_part}")
        if new_state:
            if folder_name in self._files_by_folder_cache:
                files_to_add = self._files_by_folder_cache[folder_name]
                insert_position = folder_header_index + 1
                for file_text, file_path, file_color in sorted(files_to_add):
                    file_item = QListWidgetItem(f"    {file_text}")
                    file_item.setData(Qt.UserRole, file_path)
                    if file_color:
                        file_item.setForeground(file_color)
                    self.file_list.insertItem(insert_position, file_item)
                    insert_position += 1
            if getattr(self.window, 'current_file', None):
                self.update_library_selection(self.window.current_file)
        else:
            items_to_remove = []
            for i in range(folder_header_index + 1, self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                if file_path and file_path.startswith("FOLDER_HEADER:"):
                    break
                items_to_remove.append(i)
            for i in reversed(items_to_remove):
                self.file_list.takeItem(i)

    def update_library_selection(self, file_path):
        try:
            from ui.mini_bar_visualizer import MiniBarVisualizer
        except ImportError:
            return

        def update_list_widget(list_widget):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                widget = list_widget.itemWidget(item)
                if widget and widget.objectName() == "mini_bar_visualizer":
                    list_widget.removeItemWidget(item)
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.data(Qt.UserRole) == file_path:
                    visualizer = MiniBarVisualizer(list_widget)
                    visualizer.setObjectName("mini_bar_visualizer")
                    list_widget.setItemWidget(item, visualizer)
                    break

        update_list_widget(self.file_list)
        if hasattr(self, 'kh_rando_file_list') and self.kh_rando_file_list:
            update_list_widget(self.kh_rando_file_list)

    def on_library_selection_changed(self):
        if self._updating_selection:
            return
        selected_items = self.file_list.selectedItems()
        if selected_items and hasattr(self, 'kh_rando_file_list'):
            self._updating_selection = True
            self.kh_rando_file_list.clearSelection()
            self._updating_selection = False
        self.on_library_selection_changed_common(selected_items)

    def on_library_selection_changed_common(self, selected_items):
        has_selection = len(selected_items) > 0
        single_selection = len(selected_items) == 1
        can_open_location = single_selection or (len(selected_items) == 0 and self.window.current_file is not None)
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
                    if single_selection and (ext.endswith('.scd') or ext.endswith('.wav')):
                        single_supported_selection = True
        else:
            if self.window.current_file and os.path.exists(self.window.current_file):
                ext = self.window.current_file.lower()
                if not ext.endswith('.wav'):
                    has_non_wav_files = True
                if not ext.endswith('.scd'):
                    has_non_scd_files = True
                if ext.endswith('.scd') or ext.endswith('.wav'):
                    single_supported_selection = True

        self.export_selected_btn.setEnabled(has_selection)
        self.delete_selected_btn.setEnabled(has_selection)
        enable_wav_convert = bool((has_selection and has_non_wav_files) or (not has_selection and self.window.current_file and has_non_wav_files))
        enable_scd_convert = bool((has_selection and has_non_scd_files) or (not has_selection and self.window.current_file and has_non_scd_files))
        self.convert_to_wav_btn.setEnabled(enable_wav_convert)
        self.convert_to_scd_btn.setEnabled(enable_scd_convert)
        self.open_file_location_btn.setEnabled(can_open_location)
        self.open_loop_editor_btn.setEnabled(single_supported_selection)

    def get_all_selected_items(self):
        selected_items = []
        selected_items.extend(self.file_list.selectedItems())
        if hasattr(self, 'kh_rando_file_list'):
            for item in self.kh_rando_file_list.selectedItems():
                file_path = item.data(Qt.UserRole)
                if file_path and not file_path.startswith("KH_CATEGORY_HEADER:"):
                    selected_items.append(item)
        return selected_items

    def delete_selected_files(self):
        selected_items = self.get_all_selected_items()
        if not selected_items:
            show_themed_message(self.window, QMessageBox.Information, "No Selection", "Please select one or more files to delete.")
            return

        files_to_delete = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                files_to_delete.append(file_path)

        if not files_to_delete:
            show_themed_message(self.window, QMessageBox.Warning, "No Valid Files", "No valid files found in selection.")
            return

        msg = f"🗑️  Move {len(files_to_delete)} file(s) to Recycle Bin?\n\n"
        msg += "Files can be restored from the Recycle Bin if needed.\n\n"
        msg += "Files to delete:\n" + "\n".join(f"• {os.path.basename(f)}" for f in files_to_delete[:10])
        if len(files_to_delete) > 10:
            msg += f"\n• ... and {len(files_to_delete) - 10} more"

        reply = show_themed_message(self.window, QMessageBox.Question, "Move to Recycle Bin", msg,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        deleted_count = 0
        failed_files = []
        for file_path in files_to_delete:
            if send_to_recycle_bin(file_path):
                deleted_count += 1
            else:
                failed_files.append(os.path.basename(file_path))

        if failed_files:
            msg = f"Moved {deleted_count} file(s) to Recycle Bin.\n\nFailed to delete {len(failed_files)} file(s):\n"
            msg += "\n".join(f"• {f}" for f in failed_files[:5])
            if len(failed_files) > 5:
                msg += f"\n• ... and {len(failed_files) - 5} more"
            show_themed_message(self.window, QMessageBox.Warning, "Deletion Results", msg)
        else:
            show_themed_message(self.window, QMessageBox.Information, "Files Moved", f"Successfully moved {deleted_count} file(s) to Recycle Bin.")

    def open_file_location(self):
        selected_items = self.get_all_selected_items()
        file_path = None
        source_description = ""

        if len(selected_items) == 1:
            data = selected_items[0].data(Qt.UserRole)
            if data and (data.startswith("FOLDER_HEADER:") or data.startswith("KH_CATEGORY_HEADER:")):
                if data.startswith("FOLDER_HEADER:"):
                    folder_name = data.replace("FOLDER_HEADER:", "")
                    folder_path = None
                    for folder in self.window.config.library_folders:
                        if os.path.basename(folder) == folder_name or folder == folder_name:
                            folder_path = folder
                            break
                    if folder_path and os.path.exists(folder_path):
                        file_path = folder_path
                        source_description = "selected folder"
                    else:
                        show_themed_message(self.window, QMessageBox.Warning, "Folder Not Found", f"The selected folder '{folder_name}' could not be found in your library folders.")
                        return
                elif data.startswith("KH_CATEGORY_HEADER:"):
                    kh_rando_folder = getattr(self.window.config, 'kh_rando_folder', None)
                    if kh_rando_folder and os.path.exists(kh_rando_folder):
                        file_path = kh_rando_folder
                        source_description = "KH Rando folder"
                    else:
                        show_themed_message(self.window, QMessageBox.Warning, "KH Rando Folder Not Set", "The KH Rando folder is not set or does not exist.")
                        return
            else:
                file_path = data
                source_description = "selected file"
        elif len(selected_items) == 0 and getattr(self.window, 'current_file', None):
            file_path = self.window.current_file
            source_description = "currently playing file"
        elif len(selected_items) > 1:
            show_themed_message(self.window, QMessageBox.Information, "Multiple Selection",
                              "Please select exactly one file to open its location, or use no selection to open the currently playing file's location.")
            return
        else:
            show_themed_message(self.window, QMessageBox.Information, "No File Available",
                              "Please select a file from the library or load a file to play first.")
            return

        if not file_path or not os.path.exists(file_path):
            show_themed_message(self.window, QMessageBox.Warning, "File Not Found",
                              f"The {source_description} no longer exists on disk.")
            return

        try:
            import subprocess
            import platform
            folder_path = os.path.dirname(file_path)
            if platform.system() == "Windows":
                normalized_path = os.path.normpath(file_path)
                subprocess.run(f'explorer /select,"{normalized_path}"', shell=True)
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", file_path], check=True)
            else:
                subprocess.run(["xdg-open", folder_path], check=True)

        except Exception as e:
            show_themed_message(self.window, QMessageBox.Warning, "Cannot Open Location",
                              f"Failed to open file location:\n{str(e)}")

    def convert_selected_to_wav(self):
        """Convert selected library items (or current file) to WAV via the main conversion manager."""
        if hasattr(self.window, 'conversion_manager'):
            self.window.conversion_manager.convert_selected_to_wav()

    def convert_selected_to_scd(self):
        """Convert selected library items (or current file) to SCD via the main conversion manager."""
        if hasattr(self.window, 'conversion_manager'):
            self.window.conversion_manager.convert_selected_to_scd()

    def export_selected_to_kh_rando(self):
        """Delegate export of selected items to the KH Rando manager."""
        if hasattr(self.window, 'kh_rando_manager'):
            self.window.kh_rando_manager.export_selected_to_kh_rando()

    def export_missing_to_kh_rando(self):
        """Delegate export of missing items to the KH Rando manager."""
        if hasattr(self.window, 'kh_rando_manager'):
            self.window.kh_rando_manager.export_missing_to_kh_rando()

    # Context menus
    def show_file_list_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item:
            return
        file_path = item.data(Qt.UserRole)
        if not file_path or file_path.startswith("FOLDER_HEADER"):
            return
        menu = QMenu(self.window)
        export_action = menu.addAction("Export to KH Rando")
        export_action.triggered.connect(self.export_selected_to_kh_rando)
        menu.addSeparator()

        selected_items = [item for item in self.file_list.selectedItems()
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        if len(selected_items) == 1:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.scd', '.wav']:
                loop_editor_action = menu.addAction("Open Loop Editor")
                loop_editor_action.triggered.connect(self.window.open_loop_editor)
                menu.addSeparator()
            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_file(file_path))
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_files)
        menu.exec_(self.file_list.mapToGlobal(position))

    def show_kh_rando_context_menu(self, position):
        item = self.kh_rando_file_list.itemAt(position)
        if not item:
            return
        file_path = item.data(Qt.UserRole)
        if not file_path or file_path.startswith("KH_CATEGORY_HEADER"):
            return
        menu = QMenu(self.window)
        selected_items = [item for item in self.kh_rando_file_list.selectedItems()
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("KH_CATEGORY_HEADER")]
        if len(selected_items) == 1:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.scd', '.wav']:
                loop_editor_action = menu.addAction("Open Loop Editor")
                loop_editor_action.triggered.connect(self.window.open_loop_editor)
                menu.addSeparator()
            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_file(file_path))
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_files)
        menu.exec_(self.kh_rando_file_list.mapToGlobal(position))

    def rename_file(self, file_path):
        path = Path(file_path)
        if not path.exists():
            show_themed_message(self.window, QMessageBox.Warning, "File Not Found",
                               "The file no longer exists.")
            return
        old_name = path.stem
        old_ext = path.suffix
        new_name, ok = QInputDialog.getText(
            self.window,
            "Rename File",
            f"Enter new name for '{path.name}':",
            QLineEdit.Normal,
            old_name
        )
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                return
            new_file_path = path.parent / (new_name + old_ext)
            if new_file_path.exists():
                show_themed_message(self.window, QMessageBox.Warning, "File Exists",
                                   f"A file named '{new_file_path.name}' already exists.")
                return
            try:
                path.rename(new_file_path)
                logging.info(f"Renamed file: {path} -> {new_file_path}")
                QTimer.singleShot(100, lambda: self._on_file_removed(str(path)))
                QTimer.singleShot(200, lambda: self._on_file_added(str(new_file_path)))
            except Exception as e:
                show_themed_message(self.window, QMessageBox.Critical, "Rename Error",
                                   f"Failed to rename file:\n{str(e)}")

    # File watcher and scanning
    def perform_initial_scan(self):
        if not self.library:
            return
        if hasattr(self.window, 'scan_overlay'):
            self.window.scan_overlay.show()
        self.library.scan_folders(self.window.config.library_folders, self.window.config.scan_subdirs, self.window.config.kh_rando_folder)
        if self.organize_by_folder_cb.isChecked():
            self._organize_files_by_folder()
        if hasattr(self.window, 'scan_overlay'):
            self.window.scan_overlay.hide()
        logging.info("Initial library scan completed")

    def _on_file_added(self, file_path: str):
        logging.info(f"File added: {file_path}")
        if self.library and self.library.kh_rando_exporter:
            self.library.kh_rando_exporter.refresh_existing_files()
        if self.library:
            self.library._add_single_file(Path(file_path))
        is_in_library = False
        is_in_kh_rando = False
        try:
            file_path_obj = Path(file_path).resolve()
            if self.window.config.kh_rando_folder:
                kh_rando_path = Path(self.window.config.kh_rando_folder).resolve()
                if file_path_obj.is_relative_to(kh_rando_path):
                    is_in_kh_rando = True
            if not is_in_kh_rando:
                for folder in self.window.config.library_folders:
                    folder_path = Path(folder).resolve()
                    if file_path_obj.is_relative_to(folder_path):
                        is_in_library = True
                        break
        except Exception:
            pass
        if is_in_library:
            if self.organize_by_folder_cb.isChecked() and not is_in_kh_rando:
                folder = os.path.dirname(file_path)
                folder_name = os.path.basename(folder) if folder and folder != "." else "Files (No Folder)"
                if folder_name not in self._files_by_folder_cache:
                    self._files_by_folder_cache[folder_name] = []
                display_text = os.path.basename(file_path)
                size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
                from utils.helpers import format_file_size
                display_text = f"{display_text} ({format_file_size(size)})"
                self._files_by_folder_cache[folder_name].append((display_text, file_path, None))
                self._organize_files_by_folder()
            else:
                self.filter_library_files()
        self._populate_kh_rando_list()
        self._update_kh_rando_section_counts()
        self._refresh_duplicate_status()

    def _on_file_removed(self, file_path: str):
        logging.info(f"File removed: {file_path}")
        self._remove_file_from_display(file_path)
        self._populate_kh_rando_list()
        if self.organize_by_folder_cb.isChecked():
            expanded_folders = self._get_expanded_folder_items()
            if self._files_by_folder_cache:
                for folder_name in list(self._files_by_folder_cache.keys()):
                    self._files_by_folder_cache[folder_name] = [
                        (text, fpath, color) for text, fpath, color in self._files_by_folder_cache[folder_name]
                        if fpath != file_path
                    ]
                    if not self._files_by_folder_cache[folder_name]:
                        del self._files_by_folder_cache[folder_name]
            self._organize_files_by_folder()
            self._restore_expanded_folder_items(expanded_folders)
        else:
            self.filter_library_files()
        self._update_kh_rando_section_counts()
        self._refresh_duplicate_status()

    def _on_directory_added(self, directory_path: str):
        logging.info(f"Directory added: {directory_path}")
        is_in_library = False
        try:
            dir_path_obj = Path(directory_path).resolve()
            for folder in self.window.config.library_folders:
                folder_path = Path(folder).resolve()
                if dir_path_obj.is_relative_to(folder_path):
                    is_in_library = True
                    break
        except Exception:
            pass
        if is_in_library and self.organize_by_folder_cb.isChecked():
            QTimer.singleShot(200, self._organize_files_by_folder)
        if self.window.config.kh_rando_folder:
            try:
                dir_path = Path(directory_path).resolve()
                kh_rando_path = Path(self.window.config.kh_rando_folder).resolve()
                if dir_path.is_relative_to(kh_rando_path):
                    if self.library and self.library.kh_rando_exporter:
                        self.library.kh_rando_exporter.refresh_existing_files()
                    QTimer.singleShot(200, lambda: (
                        self._update_kh_rando_categories(),
                        self._populate_kh_rando_list(),
                        self._update_kh_rando_section_counts()
                    ))
                    logging.info(f"KH Rando categories updated for new directory: {directory_path}")
            except (ValueError, OSError) as e:
                logging.warning(f"Error checking directory path: {e}")

    def _on_directory_removed(self, directory_path: str):
        logging.info(f"Directory removed: {directory_path}")
        if self.window.config.kh_rando_folder:
            try:
                dir_path = Path(directory_path).resolve()
                kh_rando_path = Path(self.window.config.kh_rando_folder).resolve()
                if dir_path.is_relative_to(kh_rando_path) or str(dir_path) == str(kh_rando_path):
                    if self.library and self.library.kh_rando_exporter:
                        self.library.kh_rando_exporter.refresh_existing_files()
                    QTimer.singleShot(200, lambda: (
                        self._update_kh_rando_categories(),
                        self._populate_kh_rando_list(),
                        self._update_kh_rando_section_counts()
                    ))
                    logging.info(f"KH Rando categories updated for removed directory: {directory_path}")
            except (ValueError, OSError) as e:
                logging.warning(f"Error checking directory path: {e}")

    def _on_file_modified(self, file_path: str):
        logging.info(f"File modified: {file_path}")

    def _remove_file_from_display(self, file_path: str):
        file_path_str = str(file_path)
        for i in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(i)
            if item and item.data(Qt.UserRole) == file_path_str:
                self.file_list.takeItem(i)
                break
        if hasattr(self.library, 'kh_rando_files_by_category'):
            for category_key in list(self.library.kh_rando_files_by_category.keys()):
                self.library.kh_rando_files_by_category[category_key] = [
                    (fpath, display) for fpath, display in self.library.kh_rando_files_by_category[category_key]
                    if fpath != file_path_str
                ]

    # Drag and drop
    def start_file_drag(self, list_widget, supportedActions):
        selected_items = [item for item in list_widget.selectedItems()
                         if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        if not selected_items:
            return
        mime_data = QMimeData()
        file_paths = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path:
                file_paths.append(file_path)
        mime_data.setText("\n".join(file_paths))

        drag = QDrag(list_widget)
        drag.setMimeData(mime_data)

        pixmap_width = 200
        pixmap_height = 40
        pixmap = QPixmap(pixmap_width, pixmap_height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.7)
        painter.setBrush(QColor(60, 60, 60))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, pixmap_width, pixmap_height, 5, 5)
        painter.setOpacity(1.0)
        painter.setPen(Qt.white)
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
        drag.exec_(Qt.CopyAction)

    def kh_rando_drag_enter_event(self, event):
        if event.mimeData().hasText() or event.source() == self.file_list:
            event.acceptProposedAction()
        else:
            event.ignore()

    def kh_rando_drag_move_event(self, event):
        if not (event.mimeData().hasText() or event.source() == self.file_list):
            event.ignore()
            return
        drop_position = event.pos()
        list_height = self.kh_rando_file_list.height()
        scroll_margin = 30
        if drop_position.y() < scroll_margin:
            current_value = self.kh_rando_file_list.verticalScrollBar().value()
            self.kh_rando_file_list.verticalScrollBar().setValue(current_value - 5)
        elif drop_position.y() > list_height - scroll_margin:
            current_value = self.kh_rando_file_list.verticalScrollBar().value()
            self.kh_rando_file_list.verticalScrollBar().setValue(current_value + 5)
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        target_item = self.kh_rando_file_list.itemAt(drop_position)
        if target_item:
            item_data = target_item.data(Qt.UserRole)
            if item_data and item_data.startswith("KH_CATEGORY_HEADER:"):
                font = target_item.font()
                font.setBold(True)
                target_item.setFont(font)
                target_item.setBackground(QColor(86, 156, 214, 80))
                self._drag_hover_item = target_item
            elif item_data and not item_data.startswith("KH_CATEGORY_HEADER:"):
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
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        event.accept()

    def kh_rando_drop_event(self, event):
        if self._drag_hover_item:
            font = self._drag_hover_item.font()
            font.setBold(False)
            self._drag_hover_item.setFont(font)
            self._drag_hover_item.setBackground(Qt.transparent)
            self._drag_hover_item = None
        if not (event.mimeData().hasText() or event.source() == self.file_list):
            event.ignore()
            return
        drop_position = event.pos()
        target_item = self.kh_rando_file_list.itemAt(drop_position)
        selected_items = [item for item in self.file_list.selectedItems()
                        if item.data(Qt.UserRole) and not item.data(Qt.UserRole).startswith("FOLDER_HEADER")]
        if not selected_items:
            event.ignore()
            return
        target_category = None
        if target_item:
            item_data = target_item.data(Qt.UserRole)
            if item_data:
                if item_data.startswith("KH_CATEGORY_HEADER:"):
                    target_category = item_data.replace("KH_CATEGORY_HEADER:", "")
                else:
                    for i in range(self.kh_rando_file_list.row(target_item), -1, -1):
                        check_item = self.kh_rando_file_list.item(i)
                        check_data = check_item.data(Qt.UserRole)
                        if check_data and check_data.startswith("KH_CATEGORY_HEADER:"):
                            target_category = check_data.replace("KH_CATEGORY_HEADER:", "")
                            break
        if not target_category:
            show_themed_message(self.window, QMessageBox.Information, "Drop Target",
                               "Please drop files onto a KH Rando category folder.")
            event.ignore()
            return
        self.export_files_to_category_instant(selected_items, target_category)
        event.acceptProposedAction()

    def export_files_to_category_instant(self, items, category):
        from ui.conversion_manager import SimpleStatusDialog
        from ui.conversion_manager import QualitySelectionDialog

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
        if not self.window.config.kh_rando_folder or not os.path.exists(self.window.config.kh_rando_folder):
            show_themed_message(self.window, QMessageBox.Warning, "KH Rando Not Set",
                               "Please set the KH Randomizer music folder first.")
            return
        selected_quality = 10
        if files_to_convert:
            quality_dialog = QualitySelectionDialog(self.window)
            apply_title_bar_theming(quality_dialog)
            if quality_dialog.exec_() != QDialog.Accepted:
                return
            selected_quality = quality_dialog.get_quality()

        final_files = scd_files.copy()
        converted_files = []
        if files_to_convert:
            status_dialog = SimpleStatusDialog("Converting Files", self.window)
            status_dialog.update_status(f"Converting {len(files_to_convert)} file(s) for export...")
            status_dialog.show()
            apply_title_bar_theming(status_dialog)
            QApplication.processEvents()
            for file_path in files_to_convert:
                try:
                    filename = os.path.basename(file_path)
                    status_dialog.update_status(f"Converting: {filename}")
                    QApplication.processEvents()
                    file_ext = os.path.splitext(file_path)[1].lower()
                    temp_scd = os.path.join(tempfile.gettempdir(), f"{os.path.splitext(filename)[0]}.scd")
                    temp_wav = None
                    source_file = file_path
                    success = False
                    try:
                        if file_ext != '.wav':
                            fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_')
                            os.close(fd)
                            success_ffmpeg = self.window.converter.convert_with_ffmpeg(file_path, temp_wav, 'wav')
                            if not success_ffmpeg:
                                if temp_wav:
                                    try:
                                        os.remove(temp_wav)
                                    except Exception:
                                        pass
                                logging.warning(f"FFmpeg conversion failed for: {filename}")
                                raise Exception("FFmpeg conversion failed")
                            source_file = temp_wav
                        original_scd_template = file_path if file_ext == '.scd' else None
                        success = self.window.converter.convert_wav_to_scd(source_file, temp_scd, original_scd_template, selected_quality)
                    finally:
                        if temp_wav:
                            try:
                                os.remove(temp_wav)
                            except Exception:
                                pass
                    if success and os.path.exists(temp_scd):
                        final_files.append(temp_scd)
                        converted_files.append(temp_scd)
                    else:
                        logging.warning(f"Conversion failed for: {filename}")
                except Exception as e:
                    logging.error(f"Error converting {file_path}: {e}")
            status_dialog.close_dialog()

        if final_files:
            export_dialog = SimpleStatusDialog("Exporting to KH Rando", self.window)
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
                    success = self.window.kh_rando_exporter.export_file(
                        file_path, category, self.window.config.kh_rando_folder
                    )
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logging.error(f"Error exporting {file_path}: {e}")
                    fail_count += 1
            export_dialog.close_dialog()
            for temp_file in converted_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass
            if success_count > 0:
                message = f"Successfully exported {success_count} file(s) to {category}"
                if fail_count > 0:
                    message += f"\n{fail_count} file(s) failed to export"
                show_themed_message(self.window, QMessageBox.Information, "Export Complete", message)
                self._refresh_duplicate_status()
                self._populate_kh_rando_list()
                self._update_kh_rando_section_counts()
            else:
                show_themed_message(self.window, QMessageBox.Warning, "Export Failed",
                                   "Failed to export files. Check the log for details.")
