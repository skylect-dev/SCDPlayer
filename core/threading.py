"""Background threading for file operations"""
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal


class FileLoadThread(QThread):
    """Thread for loading files in the background"""
    finished = pyqtSignal(str)  # Signal emitted when file loading is complete
    error = pyqtSignal(str)     # Signal emitted when an error occurs
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        
    def run(self):
        """Run the file loading operation"""
        try:
            file_path = Path(self.file_path)
            
            # Validate file exists
            if not file_path.exists():
                self.error.emit(f"File not found: {self.file_path}")
                return
                
            # Validate file is readable
            if not file_path.is_file():
                self.error.emit(f"Path is not a file: {self.file_path}")
                return
            
            # Emit success signal with the validated path
            self.finished.emit(str(file_path))
            
        except Exception as e:
            self.error.emit(f"Error loading file: {e}")
