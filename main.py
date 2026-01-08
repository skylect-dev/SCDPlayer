"""
SCDToolkit - A standalone Windows GUI application for playing SCD music files.
Supports SCD files from games like Kingdom Hearts and Final Fantasy XIV,
plus standard audio formats (WAV, MP3, OGG, FLAC).
"""
import sys
import logging
from PyQt5.QtWidgets import QApplication

from ui.main_window import SCDToolkit
from ui.widgets import SplashScreen


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
    
    # Minimal splash (pulsing icon) while the window initializes
    # splash = SplashScreen()
    # splash.show()
    # app.processEvents()  # ensure splash paints immediately
    
    # Clean up any temporary files from previous runs
    try:
        from utils.khpc_cleanup import cleanup_khpc_tools
        cleanup_khpc_tools()
    except:
        pass  # Don't fail if cleanup fails

    # Build main window asynchronously so the splash can display until ready
    window_holder = {'window': None}

    def start_main_window():
        window = SCDToolkit()
        window_holder['window'] = window
        window.show()
        # splash.fade_and_finish(window)

        # Check for .NET runtime availability and prompt for installation if missing
        def check_dotnet():
            try:
                from utils.dotnet_installer import DotNetRuntimeChecker, prompt_dotnet_install, install_dotnet_runtime
                is_available, version = DotNetRuntimeChecker.check_dotnet_installed()
                if is_available:
                    logging.info(f".NET {version} detected - SCD conversion available")
                else:
                    logging.warning(".NET 5.0 not detected - prompting for installation")
                    # Prompt user to install .NET immediately
                    if prompt_dotnet_install(window):
                        logging.info("User accepted .NET installation prompt")
                        install_dotnet_runtime(window)
                    else:
                        logging.info("User declined .NET installation")
            except Exception as e:
                logging.warning(f"Error checking .NET: {e}")

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(200, check_dotnet)

    from PyQt5.QtCore import QTimer
    QTimer.singleShot(0, start_main_window)
    
    # Check for updates is already deferred in the window initialization
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
