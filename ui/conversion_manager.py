"""Conversion features for SCDPlayer"""
import os
import tempfile
from PyQt5.QtWidgets import QMessageBox
from ui.dialogs import show_themed_message, show_themed_file_dialog


class ConversionManager:
    """Handles audio file conversions"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.converter = main_window.converter
    
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
                else:
                    show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', 'Could not convert SCD to WAV.')
            else:
                success = self.converter.convert_with_ffmpeg(self.main_window.current_file, save_path, 'wav')
                if success:
                    show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', f'WAV saved to: {save_path}')
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
            
            success = self.converter.convert_wav_to_scd(source_file, save_path)
            
            # Cleanup temp file
            if temp_wav:
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            if success:
                show_themed_message(self.main_window, QMessageBox.Information, 'Conversion Complete', f'SCD saved to: {save_path}')
            else:
                show_themed_message(self.main_window, QMessageBox.Warning, 'Conversion Failed', 'WAV to SCD conversion is not yet fully implemented.')
