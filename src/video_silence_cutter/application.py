import sys
import os
import platform
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .utils.logging_config import setup_logging
from .services.settings_service import SettingsService
from .gui.main_window import MainWindow

logger = logging.getLogger("VideoSilenceCutter")

def main():
    # 1. Logging setup
    log_file = setup_logging()

    logger.info("=== VideoSilenceCutter 起動 ===")
    logger.info(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    logger.info(f"Architecture: {platform.machine()}")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Log File Path: {log_file}")

    # 2. PySide6 App setup
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("VideoSilenceCutter")
    app.setOrganizationName("jp.local")

    settings_service = SettingsService()

    # 3. Create Main Window
    window = MainWindow(settings_service)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
