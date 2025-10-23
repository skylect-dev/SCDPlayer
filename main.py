"""
SCDToolkit - A standalone Windows GUI application for playing SCD music files.
Supports SCD files from games like Kingdom Hearts and Final Fantasy XIV,
plus standard audio formats (WAV, MP3, OGG, FLAC).
"""
import sys
import logging
from PyQt5.QtWidgets import QApplication

from ui.main_window import SCDToolkit


def main():
    """Main application entry point"""
    # Configure logging for debugging
    logging.basicConfig(
        level=logging.INFO,  # Changed from DEBUG to INFO for cleaner output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('scdtoolkit_debug.log')
        ]
    )
    
    app = QApplication(sys.argv)
    
    # Clean up any temporary files from previous runs
    try:
        from utils.khpc_cleanup import cleanup_khpc_tools
        cleanup_khpc_tools()
    except:
        pass  # Don't fail if cleanup fails
    
    # Create main window (no progress callback needed without splash)
    window = SCDToolkit()
    
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
    
    # Show main window
    window.show()
    
    # Check for updates after UI is loaded
    window.check_for_updates_startup()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
