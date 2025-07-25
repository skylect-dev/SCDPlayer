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
    
    # Helper function to update splash with consistent timing
    def update_splash(message, delay=0.3):
        splash.showMessage(message, Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        app.processEvents()
        if delay > 0:
            time.sleep(delay)
    
    # Loading sequence
    update_splash("Initializing audio system...", 0.5)
    update_splash("Loading interface...", 0.3)
    
    # Create main window
    window = SCDPlayer()
    
    # Finalize splash
    update_splash("Ready!", 0.2)
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
