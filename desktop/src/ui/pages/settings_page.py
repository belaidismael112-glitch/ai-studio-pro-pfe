"""Settings page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt

from core.config import AppConfig
from core.theme import ThemeManager


class SettingsPage(QWidget):
    """Settings page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig.load()
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup settings page UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(32)
        
        # Header
        header = QLabel("Settings")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        layout.addWidget(header)
        
        # API Settings
        api_group = self.create_group("API Configuration")
        
        api_layout = QVBoxLayout()
        
        api_url_label = QLabel("API Base URL")
        api_url_label.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        api_layout.addWidget(api_url_label)
        
        self.api_url_input = QLineEdit()
        self.api_url_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
            }
        """)
        api_layout.addWidget(self.api_url_input)
        
        api_group.layout().addLayout(api_layout)
        layout.addWidget(api_group)
        
        # Appearance Settings
        appearance_group = self.create_group("Appearance")
        
        appearance_layout = QVBoxLayout()
        
        theme_label = QLabel("Theme")
        theme_label.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        appearance_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
            }
        """)
        appearance_layout.addWidget(self.theme_combo)
        
        appearance_group.layout().addLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Download Settings
        download_group = self.create_group("Downloads")
        
        download_layout = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        
        path_label = QLabel("Download Folder")
        path_label.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        download_layout.addWidget(path_label)
        
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
            }
        """)
        path_layout.addWidget(self.path_input, 1)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f3f46;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
            }
            QPushButton:hover {
                background-color: #52525b;
            }
        """)
        browse_btn.clicked.connect(self.on_browse)
        path_layout.addWidget(browse_btn)
        
        download_layout.addLayout(path_layout)
        download_group.layout().addLayout(download_layout)
        layout.addWidget(download_group)
        
        # Default Settings
        defaults_group = self.create_group("Default Generation Settings")
        
        defaults_layout = QVBoxLayout()
        
        # Default image size
        img_size_layout = QHBoxLayout()
        
        img_size_label = QLabel("Default Image Size:")
        img_size_label.setStyleSheet("color: #a1a1aa;")
        img_size_layout.addWidget(img_size_label)
        
        self.img_size_combo = QComboBox()
        self.img_size_combo.addItems([
            "512x512",
            "768x768",
            "1024x1024",
            "1024x576",
            "1920x1080",
        ])
        self.img_size_combo.setStyleSheet("""
            QComboBox {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 8px;
                color: #ffffff;
            }
        """)
        img_size_layout.addWidget(self.img_size_combo)
        img_size_layout.addStretch()
        
        defaults_layout.addLayout(img_size_layout)
        
        # Default video duration
        video_dur_layout = QHBoxLayout()
        
        video_dur_label = QLabel("Default Video Duration:")
        video_dur_label.setStyleSheet("color: #a1a1aa;")
        video_dur_layout.addWidget(video_dur_label)
        
        self.video_dur_combo = QComboBox()
        self.video_dur_combo.addItems(["2 seconds", "4 seconds", "8 seconds", "16 seconds"])
        self.video_dur_combo.setStyleSheet("""
            QComboBox {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 8px;
                color: #ffffff;
            }
        """)
        video_dur_layout.addWidget(self.video_dur_combo)
        video_dur_layout.addStretch()
        
        defaults_layout.addLayout(video_dur_layout)
        
        defaults_group.layout().addLayout(defaults_layout)
        layout.addWidget(defaults_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedHeight(48)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        save_btn.clicked.connect(self.on_save)
        layout.addWidget(save_btn)
        
        layout.addStretch()
    
    def create_group(self, title: str) -> QFrame:
        """Create a settings group"""
        group = QFrame()
        group.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
        """)
        layout.addWidget(title_label)
        
        return group
    
    def load_settings(self):
        """Load current settings"""
        self.api_url_input.setText(self.config.api_base_url)
        self.path_input.setText(self.config.download_path)
        self.theme_combo.setCurrentIndex(0 if self.config.dark_mode else 1)
    
    def on_browse(self):
        """Browse for download folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            self.config.download_path,
        )
        if folder:
            self.path_input.setText(folder)
    
    def on_save(self):
        """Save settings"""
        self.config.api_base_url = self.api_url_input.text()
        self.config.download_path = self.path_input.text()
        self.config.dark_mode = self.theme_combo.currentIndex() == 0
        
        self.config.save()
        
        QMessageBox.information(self, "Success", "Settings saved successfully!")
