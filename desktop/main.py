"""
AI Studio Pro - Desktop Application
Professional AI Image & Video Generation Platform
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication, QTimer
from PySide6.QtGui import QFont, QFontDatabase

from ui.main_window import MainWindow
from core.config import AppConfig
from core.theme import ThemeManager
from core.updater import Updater
from core.version import APP_VERSION


def setup_application():
    """Setup application configuration"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Application metadata
    QCoreApplication.setOrganizationName("AIStudioPro")
    QCoreApplication.setOrganizationDomain("aistudiopro.com")
    QCoreApplication.setApplicationName("AI Studio Pro")
    QCoreApplication.setApplicationVersion(APP_VERSION)


def load_fonts():
    """Load custom fonts"""
    font_db = QFontDatabase()
    
    # Load Inter font if available
    fonts_dir = Path(__file__).parent / "assets" / "fonts"
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            font_db.addApplicationFont(str(font_file))
    
    # Set default font
    default_font = QFont("Inter", 10)
    if "Inter" not in font_db.families():
        default_font = QFont("Segoe UI", 10)  # Windows
        if sys.platform == "darwin":
            default_font = QFont("SF Pro", 10)  # macOS
    
    QApplication.setFont(default_font)


def main():
    """Main entry point"""
    setup_application()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Load fonts
    load_fonts()
    
    # Initialize theme
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app)
    
    # Load configuration
    config = AppConfig.load()
    
    # Create and show main window
    window = MainWindow(config)
    window.show()

    # Non-blocking update check
    def _check_updates():
        updater = Updater(config.api_base_url)
        info = updater.check()
        if info:
            updater.prompt_and_update(window, info)

    QTimer.singleShot(1500, _check_updates)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
