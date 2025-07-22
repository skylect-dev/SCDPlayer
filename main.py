"""
SCDPlayer - A standalone Windows GUI application for playing SCD music files.
Supports SCD files from games like Kingdom Hearts and Final Fantasy XIV,
plus standard audio formats (WAV, MP3, OGG, FLAC).
"""
import sys
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.main_window import SCDPlayer
from ui.widgets import SplashScreen


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()  # Allow splash to show
    
    # Simulate loading time and create main window
    splash.showMessage("Initializing audio system...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.5)  # Brief pause
    
    splash.showMessage("Loading interface...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.3)
    
    # Create main window
    window = SCDPlayer()
    
    # Show main window and close splash
    splash.showMessage("Ready!", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
    app.processEvents()
    time.sleep(0.2)
    
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
