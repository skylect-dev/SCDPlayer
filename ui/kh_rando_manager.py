"""KH Rando management features for SCDPlayer"""
import os
import tempfile
import logging
import time
from PyQt5.QtWidgets import QMessageBox, QDialog, QProgressDialog, QApplication
from PyQt5.QtCore import Qt, QTimer
from core.kh_rando import KHRandoExportDialog
from ui.dialogs import show_themed_message
from ui.conversion_manager import SimpleStatusDialog


class KHRandoManager:
    """Handles KH Rando export and management operations"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.converter = main_window.converter
        self.kh_rando_exporter = main_window.kh_rando_exporter
        self.config = main_window.config
        self.file_list = main_window.file_list
        self.library = main_window.library
    
    def export_selected_to_kh_rando(self):
        """Export selected files to KH Rando music folder (auto-converting if needed)"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            show_themed_message(self.main_window, QMessageBox.Information, "No Selection", "Please select one or more files to export.")
            return
        
        # Get file paths and separate SCD vs non-SCD files
        scd_files = []
        files_to_convert = []
        
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext == '.scd':
                    scd_files.append(file_path)
                elif file_ext in ['.wav', '.mp3', '.ogg', '.flac']:
                    files_to_convert.append(file_path)
        
        # Show info about conversion if needed
        if files_to_convert:
            convert_msg = f"""Auto-Convert to SCD for KH Rando Export

{len(files_to_convert)} non-SCD file(s) will be automatically converted to SCD format for export:
""" + "\n".join(f"• {os.path.basename(f)}" for f in files_to_convert[:5])
            
            if len(files_to_convert) > 5:
                convert_msg += f"\n• ... and {len(files_to_convert) - 5} more"
                
            convert_msg += f"\n\n{len(scd_files)} SCD file(s) will be exported directly."
            convert_msg += "\n\nContinue with export?"
            
            reply = show_themed_message(self.main_window, QMessageBox.Question, "Auto-Convert Files", convert_msg,
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes)
            if reply != QMessageBox.Yes:
                return
        
        # Prepare final file list (with conversions)
        final_files = scd_files.copy()
        converted_files = []
        
        # Convert non-SCD files to SCD with status indicator
        if files_to_convert:
            # Create simple status dialog
            status_dialog = SimpleStatusDialog("Converting Files", self.main_window)
            status_dialog.update_status("Preparing files for KH Rando export...")
            status_dialog.show()
            
            # Apply theme to status dialog
            try:
                from ui.styles import apply_title_bar_theming
                apply_title_bar_theming(status_dialog)
            except:
                pass
            
            for i, file_path in enumerate(files_to_convert):
                try:
                    filename = os.path.basename(file_path)
                    current_file = i + 1
                    total_files = len(files_to_convert)
                    
                    status_text = f"Converting {filename}...\n\nFile {current_file} of {total_files}"
                    status_dialog.update_status(status_text)
                    
                    # Create temp SCD file with original name
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    temp_scd = os.path.join(tempfile.gettempdir(), f"{base_name}.scd")
                    
                    # Convert to WAV first if needed
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext == '.wav':
                        source_wav = file_path
                    else:
                        source_wav = self.converter.convert_to_wav_temp(file_path)
                        if not source_wav:
                            continue
                    
                    # Convert WAV to SCD
                    if self.converter.convert_wav_to_scd(source_wav, temp_scd):
                        final_files.append(temp_scd)
                        converted_files.append(temp_scd)
                
                except Exception as e:
                    logging.error(f"Failed to convert {file_path}: {e}")
            
            status_dialog.update_status(f"Conversion complete!\n\nProcessed {len(files_to_convert)} files")
            QApplication.processEvents()
            import time
            time.sleep(1)  # Brief pause to show completion
            status_dialog.close_dialog()
        
        if not final_files:
            show_themed_message(self.main_window, QMessageBox.Warning, "No Valid Files", "No files could be prepared for export.")
            return
        
        # Show export dialog
        dialog = KHRandoExportDialog(final_files, self.kh_rando_exporter, self.main_window)
        if dialog.exec_() == QDialog.Accepted:
            # Clean up temporary converted files
            for temp_file in converted_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            # Refresh library to show updated KH Rando status
            if hasattr(self.main_window, 'library') and self.library:
                self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
        else:
            # Clean up temporary files if user cancelled
            for temp_file in converted_files:
                try:
                    os.remove(temp_file)
                except:
                    pass

    def export_missing_to_kh_rando(self):
        """Export all library files that are missing from KH Rando folder"""
        if not self.config.kh_rando_folder:
            show_themed_message(self.main_window, QMessageBox.Warning, "No KH Rando Folder", "Please select a KH Rando folder first.")
            return
        
        # Get all audio files that are not in KH Rando folder
        missing_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext in ['.scd', '.wav', '.mp3', '.ogg', '.flac']:
                    # Double-check: use both color coding and direct KH Rando check
                    text_color = item.foreground().color().name() if item.foreground().color().isValid() else '#ffffff'
                    is_colored = text_color in ['#90ee90', '#ffa500']  # Green or orange
                    
                    # Also check directly using the KH Rando exporter
                    filename = os.path.basename(file_path)
                    kh_categories = self.kh_rando_exporter.is_file_in_kh_rando(filename)
                    is_in_kh_rando = len(kh_categories) > 0
                    
                    # File is missing if it's not colored AND not found in KH Rando
                    if not is_colored and not is_in_kh_rando:
                        missing_files.append(file_path)
        
        if not missing_files:
            show_themed_message(self.main_window, QMessageBox.Information, "No Missing Files", "All audio files in your library are already in the KH Rando folder.")
            return
        
        # Separate SCD files from files that need conversion
        scd_files = []
        files_to_convert = []
        for file_path in missing_files:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.scd':
                scd_files.append(file_path)
            else:
                files_to_convert.append(file_path)
        
        # Show confirmation with conversion info
        total_count = len(missing_files)
        msg = f"Export {total_count} missing audio files to KH Rando?\n\n"
        
        if scd_files:
            msg += f"• {len(scd_files)} SCD files (direct export)\n"
        if files_to_convert:
            msg += f"• {len(files_to_convert)} files to convert to SCD first\n"
        
        msg += "\nFiles to export:\n" + "\n".join(f"• {os.path.basename(f)}" for f in missing_files[:10])
        if len(missing_files) > 10:
            msg += f"\n• ... and {len(missing_files) - 10} more"
        
        reply = show_themed_message(self.main_window, QMessageBox.Question, "Export Missing Files", msg,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            return
        
        # Convert non-SCD files and prepare final list
        final_files = scd_files.copy()
        converted_files = []
        
        if files_to_convert:
            for file_path in files_to_convert:
                try:
                    # Create temp SCD file with original name
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    temp_scd = os.path.join(tempfile.gettempdir(), f"{base_name}.scd")
                    
                    # Convert to WAV first if needed
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext == '.wav':
                        source_wav = file_path
                    else:
                        source_wav = self.converter.convert_to_wav_temp(file_path)
                        if not source_wav:
                            continue
                    
                    # Convert WAV to SCD
                    if self.converter.convert_wav_to_scd(source_wav, temp_scd):
                        final_files.append(temp_scd)
                        converted_files.append(temp_scd)
                
                except Exception as e:
                    logging.error(f"Failed to convert {file_path}: {e}")
        
        # Show export dialog
        dialog = KHRandoExportDialog(final_files, self.kh_rando_exporter, self.main_window)
        if dialog.exec_() == QDialog.Accepted:
            # Clean up temporary converted files
            for temp_file in converted_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
            # Refresh library to show updated status
            if hasattr(self.main_window, 'library') and self.library:
                self.library.scan_folders(self.config.library_folders, self.config.scan_subdirs, self.config.kh_rando_folder)
        else:
            # Clean up temporary files if user cancelled
            for temp_file in converted_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
