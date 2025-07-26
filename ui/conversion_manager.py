"""Conversion features for SCDPlayer"""
import os
import tempfile
from PyQt5.QtWidgets import QMessageBox, QLabel, QDialog, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from ui.dialogs import show_themed_message, show_themed_file_dialog


class SimpleStatusDialog(QDialog):
    """Simple text-based status dialog for operations"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(300, 100)
        self.setMaximumSize(400, 150)
        
        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
    def update_status(self, message):
        """Update the status message"""
        self.status_label.setText(message)
        QApplication.processEvents()
        
    def close_dialog(self):
        """Close the dialog"""
        self.close()


class ConversionWorker(QThread):
    """Worker thread for conversion operations with progress tracking"""
    progress_update = pyqtSignal(int, str)  # progress percentage, status message
    conversion_complete = pyqtSignal(bool, str)  # success, result message
    
    def __init__(self, converter, operation_type, files, output_dir=None):
        super().__init__()
        self.converter = converter
        self.operation_type = operation_type  # 'to_wav' or 'to_scd'
        self.files = files
        self.output_dir = output_dir
        
    def run(self):
        """Run the conversion operation"""
        try:
            total_files = len(self.files)
            success_count = 0
            
            for i, file_path in enumerate(self.files):
                if self.isInterruptionRequested():
                    return
                    
                filename = os.path.basename(file_path)
                self.progress_update.emit(
                    int((i / total_files) * 100),
                    f"Converting {filename}..."
                )
                
                if self.operation_type == 'to_wav':
                    success = self._convert_to_wav(file_path)
                elif self.operation_type == 'to_scd':
                    success = self._convert_to_scd(file_path)
                else:
                    success = False
                    
                if success:
                    success_count += 1
                    
            self.progress_update.emit(100, "Conversion complete!")
            
            if success_count == total_files:
                self.conversion_complete.emit(True, f"Successfully converted {success_count} file(s)")
            elif success_count > 0:
                self.conversion_complete.emit(True, f"Converted {success_count} of {total_files} files")
            else:
                self.conversion_complete.emit(False, "No files were converted successfully")
                
        except Exception as e:
            self.conversion_complete.emit(False, f"Conversion error: {str(e)}")
    
    def _convert_to_wav(self, file_path):
        """Convert a single file to WAV"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.wav':
                return True  # Already WAV
                
            if self.output_dir:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(self.output_dir, f"{base_name}.wav")
            else:
                output_path = os.path.splitext(file_path)[0] + '.wav'
                
            if file_ext == '.scd':
                result = self.converter.convert_scd_to_wav(file_path, out_path=output_path)
                return result is not None
            else:
                return self.converter.convert_with_ffmpeg(file_path, output_path, 'wav')
        except Exception:
            return False
    
    def _convert_to_scd(self, file_path):
        """Convert a single file to SCD"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.scd':
                return True  # Already SCD
                
            if self.output_dir:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(self.output_dir, f"{base_name}.scd")
            else:
                output_path = os.path.splitext(file_path)[0] + '.scd'
            
            # Convert to WAV first if needed
            temp_wav = None
            source_file = file_path
            
            if file_ext != '.wav':
                fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_')
                os.close(fd)
                
                success = self.converter.convert_with_ffmpeg(file_path, temp_wav, 'wav')
                if not success:
                    if temp_wav:
                        try:
                            os.remove(temp_wav)
                        except:
                            pass
                    return False
                source_file = temp_wav
            
            # Convert WAV to SCD
            # If original file was SCD, use it as template to preserve codec/compression
            original_scd_template = file_path if file_ext == '.scd' else None
            success = self.converter.convert_wav_to_scd(source_file, output_path, original_scd_template)
            
            # Cleanup temp file
            if temp_wav:
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            return success
        except Exception:
            return False


class ConversionManager:
    """Handles audio file conversions"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.converter = main_window.converter
        self.conversion_worker = None
        
    def convert_selected_to_wav(self):
        """Convert selected library files to WAV"""
        selected_items = self.main_window.file_list.selectedItems()
        if not selected_items:
            show_themed_message(self.main_window, QMessageBox.Information, 'No Selection', 'Please select one or more files to convert.')
            return
            
        # Get file paths
        files_to_convert = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                files_to_convert.append(file_path)
        
        if not files_to_convert:
            show_themed_message(self.main_window, QMessageBox.Warning, 'No Valid Files', 'No valid files found in selection.')
            return
        
        # Get output directory
        output_dir = show_themed_file_dialog(
            self.main_window, "directory", 'Select Output Directory for WAV Files'
        )
        
        if output_dir:
            self._start_conversion_with_progress(files_to_convert, 'to_wav', output_dir)
    
    def convert_selected_to_scd(self):
        """Convert selected library files to SCD"""
        selected_items = self.main_window.file_list.selectedItems()
        if not selected_items:
            show_themed_message(self.main_window, QMessageBox.Information, 'No Selection', 'Please select one or more files to convert.')
            return
            
        # Get file paths
        files_to_convert = []
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                files_to_convert.append(file_path)
        
        if not files_to_convert:
            show_themed_message(self.main_window, QMessageBox.Warning, 'No Valid Files', 'No valid files found in selection.')
            return
        
        # Show confirmation dialog with file list
        files_preview = "\n".join(f"• {os.path.basename(f)}" for f in files_to_convert[:5])
        if len(files_to_convert) > 5:
            files_preview += f"\n• ... and {len(files_to_convert) - 5} more"
            
        convert_msg = f"Convert {len(files_to_convert)} file(s) to SCD format?\n\n{files_preview}"
        
        reply = show_themed_message(self.main_window, QMessageBox.Question, 'Convert to SCD', convert_msg,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            return
            
        # Get output directory
        output_dir = show_themed_file_dialog(
            self.main_window, "directory", 'Select Output Directory for SCD Files'
        )
        
        if output_dir:
            self._start_conversion_with_progress(files_to_convert, 'to_scd', output_dir)
    
    def _start_conversion_with_progress(self, files, operation_type, output_dir):
        """Start conversion operation with status dialog"""
        # Create simple status dialog
        operation_name = "WAV" if operation_type == 'to_wav' else "SCD"
        self.status_dialog = SimpleStatusDialog(f"Converting to {operation_name}", self.main_window)
        self.status_dialog.show()
        
        # Apply theme to status dialog
        try:
            from ui.styles import apply_title_bar_theming
            apply_title_bar_theming(self.status_dialog)
        except:
            pass
        
        # Create and start worker thread
        self.conversion_worker = ConversionWorker(self.converter, operation_type, files, output_dir)
        
        # Connect signals
        self.conversion_worker.progress_update.connect(
            lambda progress, message: self._update_status(progress, message)
        )
        self.conversion_worker.conversion_complete.connect(
            lambda success, message: self._conversion_finished(success, message)
        )
        
        # Start conversion
        self.conversion_worker.start()
    
    def _update_status(self, progress, message):
        """Update status dialog with text-based progress"""
        total_files = len(self.conversion_worker.files) if hasattr(self, 'conversion_worker') else 1
        current_file = int((progress / 100) * total_files) + 1
        
        if progress < 100:
            status_text = f"{message}\n\nFile {current_file} of {total_files} ({progress}%)"
        else:
            status_text = f"{message}\n\nCompleted all {total_files} files!"
            
        self.status_dialog.update_status(status_text)
    
    def _conversion_finished(self, success, message):
        """Handle conversion completion"""
        self.status_dialog.close_dialog()
        
        if success:
            show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', message)
            
            # Refresh library to show new converted files
            if hasattr(self.main_window, 'library') and self.main_window.library:
                self.main_window.library.scan_folders(
                    self.main_window.config.library_folders, 
                    self.main_window.config.scan_subdirs, 
                    self.main_window.config.kh_rando_folder
                )
        else:
            show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', message)
        
        # Clean up worker
        if self.conversion_worker:
            self.conversion_worker.quit()
            self.conversion_worker.wait()
            self.conversion_worker = None
    
    # Legacy methods for backward compatibility (currently loaded file conversion)
    def convert_current_to_wav(self):
        """Convert currently loaded audio file to WAV and save"""
        if not self.main_window.current_file:
            show_themed_message(self.main_window, QMessageBox.Warning, 'No File Loaded', 'Please load an audio file first.')
            return
            
        file_ext = os.path.splitext(self.main_window.current_file)[1].lower()
        if file_ext == '.wav':
            show_themed_message(self.main_window, QMessageBox.Information, 'Already WAV', 'The loaded file is already in WAV format.')
            return
            
        save_path = show_themed_file_dialog(
            self.main_window, "save", 'Save WAV As', 
            os.path.splitext(self.main_window.current_file)[0] + '.wav', 
            'WAV Files (*.wav)'
        )
        
        if save_path:
            if file_ext == '.scd':
                wav = self.converter.convert_scd_to_wav(self.main_window.current_file, out_path=save_path)
                if wav:
                    show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', f'WAV saved to: {save_path}')
                    # Refresh library to show new converted file
                    if hasattr(self.main_window, 'library') and self.main_window.library:
                        self.main_window.library.scan_folders(
                            self.main_window.config.library_folders, 
                            self.main_window.config.scan_subdirs, 
                            self.main_window.config.kh_rando_folder
                        )
                else:
                    show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', 'Could not convert SCD to WAV.')
            else:
                success = self.converter.convert_with_ffmpeg(self.main_window.current_file, save_path, 'wav')
                if success:
                    show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', f'WAV saved to: {save_path}')
                    # Refresh library to show new converted file
                    if hasattr(self.main_window, 'library') and self.main_window.library:
                        self.main_window.library.scan_folders(
                            self.main_window.config.library_folders, 
                            self.main_window.config.scan_subdirs, 
                            self.main_window.config.kh_rando_folder
                        )
                else:
                    show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', f'Could not convert {file_ext} to WAV.')

    def convert_current_to_scd(self):
        """Convert currently loaded audio file to SCD"""
        if not self.main_window.current_file:
            show_themed_message(self.main_window, QMessageBox.Warning, 'No File Loaded', 'Please load an audio file first.')
            return
            
        file_ext = os.path.splitext(self.main_window.current_file)[1].lower()
        if file_ext == '.scd':
            show_themed_message(self.main_window, QMessageBox.Information, 'Already SCD', 'The loaded file is already in SCD format.')
            return
        
        # Show simple conversion dialog
        filename = os.path.basename(self.main_window.current_file)
        reply = show_themed_message(self.main_window, QMessageBox.Question, 'Convert to SCD', 
                                   f'Convert {filename} to SCD format?', 
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.Yes)
        
        if reply != QMessageBox.Yes:
            return
            
        save_path = show_themed_file_dialog(
            self.main_window, "save", 'Save SCD As', 
            os.path.splitext(self.main_window.current_file)[0] + '.scd', 
            'SCD Files (*.scd)'
        )
        
        if save_path:
            # Convert to WAV first if needed
            temp_wav = None
            source_file = self.main_window.current_file
            
            if file_ext != '.wav':
                fd, temp_wav = tempfile.mkstemp(suffix='.wav', prefix='scdconv_')
                os.close(fd)
                
                success = self.converter.convert_with_ffmpeg(self.main_window.current_file, temp_wav, 'wav')
                if not success:
                    show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', 'Could not convert to WAV for SCD conversion.')
                    if temp_wav:
                        try:
                            os.remove(temp_wav)
                        except:
                            pass
                    return
                source_file = temp_wav
            
            # Convert WAV to SCD using original file as template if it's SCD
            original_scd_template = self.main_window.current_file if file_ext == '.scd' else None
            success = self.converter.convert_wav_to_scd(source_file, save_path, original_scd_template)
            
            # Cleanup temp file
            if temp_wav:
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            if success:
                show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', f'SCD saved to: {save_path}')
                # Refresh library to show new converted file
                if hasattr(self.main_window, 'library') and self.main_window.library:
                    self.main_window.library.scan_folders(
                        self.main_window.config.library_folders, 
                        self.main_window.config.scan_subdirs, 
                        self.main_window.config.kh_rando_folder
                    )
            else:
                show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', 'Could not complete SCD conversion.')
