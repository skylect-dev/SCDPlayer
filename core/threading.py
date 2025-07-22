"""Background threading for file operations"""
import os
from PyQt5.QtCore import QThread, pyqtSignal


class FileLoadThread(QThread):
    """Thread for loading files in the background"""
    finished = pyqtSignal(str)  # Signal emitted when file loading is complete
    error = pyqtSignal(str)     # Signal emitted when an error occurs
    
    def __init__(self, file_path: str):
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
