"""Dialog utilities and themed dialogs for SCDPlayer"""
import sys
import ctypes
import logging
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtCore import Qt


def apply_title_bar_theming(dialog):
    """Apply title bar theming to any dialog"""
    if sys.platform != "win32":
        return
        
    try:
        from ctypes import wintypes
        
        # Windows 11 dark mode constants
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        # Get window handle
        hwnd = int(dialog.winId())
        
        # Try to enable dark title bar
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)),
            ctypes.sizeof(ctypes.c_int)
        )
    except (AttributeError, OSError) as e:
        logging.debug(f"Title bar theming not available: {e}")


def show_themed_message(parent, icon, title, text, buttons=QMessageBox.Ok, default_button=None):
    """Show a message box with title bar theming"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(buttons)
    if default_button:
        msg_box.setDefaultButton(default_button)
    
    # Apply title bar theming
    apply_title_bar_theming(msg_box)
    
    return msg_box.exec_()


def _create_file_dialog(parent, title, dialog_type="open"):
    """Factory function to create file dialogs"""
    dialog = QFileDialog(parent)
    dialog.setWindowTitle(title)
    
    if dialog_type == "save":
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
    elif dialog_type == "directory":
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
    else:  # default to "open"
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
    
    apply_title_bar_theming(dialog)
    return dialog


def show_themed_file_dialog(parent, dialog_type, title, directory="", filter=""):
    """Show a file dialog with title bar theming"""
    dialog = _create_file_dialog(parent, title, dialog_type)
    
    # Set directory or file selection
    if directory:
        if dialog_type == "save":
            dialog.selectFile(directory)
        else:
            dialog.setDirectory(directory)
    
    # Set file filter
    if filter:
        dialog.setNameFilter(filter)
    
    # Execute dialog and return result
    if dialog.exec_() == QFileDialog.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None
