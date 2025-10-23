"""
SCDPlayer - A standalone Windows GUI application for playing SCD music files.
Supports SCD files from games like Kingdom Hearts and Final Fantasy XIV,
plus standard audio formats (WAV, MP3, OGG, FLAC).
"""
import sys
import time
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.main_window import SCDPlayer
from ui.widgets import SplashScreen


def main():
    """Main application entry point"""
    # Configure logging for debugging
    logging.basicConfig(
        level=logging.INFO,  # Changed from DEBUG to INFO for cleaner output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('scdplayer_debug.log')
        ]
    )
    
    app = QApplication(sys.argv)
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    
    # Helper function to update splash (no artificial delays for speed)
    def update_splash(message, delay=0):
        splash.showMessage(message, Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        app.processEvents()
        if delay > 0:
            time.sleep(delay)
    
    # Loading sequence with more detail
    update_splash("Starting SCDPlayer...")
    
    update_splash("Cleaning up temporary files...")
    # Clean up any temporary files from previous runs
    try:
        from utils.khpc_cleanup import cleanup_khpc_tools
        cleanup_khpc_tools()
    except:
        pass  # Don't fail if cleanup fails
    
    update_splash("Loading configuration...")
    
    update_splash("Initializing audio system...")
    
    # Create main window with progress callback
    window = SCDPlayer(progress_callback=update_splash)
    
    update_splash("Checking .NET runtime...")
    # Check for .NET runtime availability (non-blocking)
    try:
        from utils.dotnet_installer import DotNetRuntimeChecker
        is_available, version = DotNetRuntimeChecker.check_dotnet_installed()
        if is_available:
            logging.info(f".NET {version} detected - SCD conversion available")
        else:
            logging.info(".NET not detected - SCD conversion will prompt for installation")
    except Exception as e:
        logging.warning(f"Error checking .NET: {e}")
    
    update_splash("Finalizing...")
    
    # Finalize splash
    update_splash("Ready!")
    window.show()
    splash.finish(window)
    
    # Check for updates after UI is loaded
    window.check_for_updates_startup()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
