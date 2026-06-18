"""Main application window"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QFrame,
    QMessageBox, QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon

from core.config import AppConfig
from core.theme import ThemeManager
from api.client import get_api_client

from .sidebar import Sidebar
from .pages.login_page import LoginPage
from .pages.dashboard_page import DashboardPage
from .pages.image_generation_page import ImageGenerationPage
from .pages.video_generation_page import VideoGenerationPage
from .pages.history_page import HistoryPage
from .pages.credits_page import CreditsPage
from .pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    """Main application window"""
    
    user_logged_in = Signal(dict)
    user_logged_out = Signal()
    credits_updated = Signal(int)
    
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.api_client = get_api_client(config.api_base_url)
        self.current_user = None
        
        self.setup_ui()
        self.setup_timer()
        
        # Try to restore session
        if self.config.access_token:
            self.api_client.set_token(self.config.access_token)
            self.restore_session()
    
    def setup_ui(self):
        """Setup user interface"""
        self.setWindowTitle("AI Studio Pro")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self.on_nav_clicked)
        self.sidebar.logout_clicked.connect(self.logout)
        layout.addWidget(self.sidebar)
        
        # Content area
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack, 1)
        
        # Pages
        self.login_page = LoginPage()
        self.login_page.login_success.connect(self.on_login_success)
        self.login_page.register_requested.connect(self.show_register)
        
        self.dashboard_page = DashboardPage()
        self.image_gen_page = ImageGenerationPage()
        self.video_gen_page = VideoGenerationPage()
        self.history_page = HistoryPage()
        self.credits_page = CreditsPage()
        self.settings_page = SettingsPage()
        
        # Add pages to stack
        self.content_stack.addWidget(self.login_page)      # 0
        self.content_stack.addWidget(self.dashboard_page)  # 1
        self.content_stack.addWidget(self.image_gen_page)  # 2
        self.content_stack.addWidget(self.video_gen_page)  # 3
        self.content_stack.addWidget(self.history_page)    # 4
        self.content_stack.addWidget(self.credits_page)    # 5
        self.content_stack.addWidget(self.settings_page)   # 6
        
        # Show login page initially
        self.show_login_page()
    
    def setup_timer(self):
        """Setup refresh timer"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 seconds
    
    def restore_session(self):
        """Try to restore user session"""
        response = self.api_client.get_current_user()
        if response.success:
            self.on_login_success(response.data)
        else:
            # Token expired, clear it
            self.config.clear_auth()
            self.api_client.clear_token()
    
    def on_login_success(self, user_data: dict):
        """Handle successful login"""
        self.current_user = user_data
        
        # Save tokens
        if "access_token" in user_data:
            self.config.access_token = user_data["access_token"]
            self.config.refresh_token = user_data.get("refresh_token", "")
            self.api_client.set_token(user_data["access_token"])
        
        self.config.user_email = user_data.get("email", "")
        self.config.user_credits = user_data.get("credits", 0)
        self.config.save()
        
        # Update UI
        self.sidebar.set_user_info(
            user_data.get("email", ""),
            user_data.get("credits", 0),
        )
        self.sidebar.show_logged_in(True)
        
        # Emit signal
        self.user_logged_in.emit(user_data)
        
        # Show dashboard
        self.show_dashboard()
        
        # Refresh data
        self.refresh_data()
    
    def logout(self):
        """Logout user"""
        self.current_user = None
        
        # Clear config
        self.config.clear_auth()
        self.api_client.clear_token()
        
        # Update UI
        self.sidebar.show_logged_in(False)
        
        # Emit signal
        self.user_logged_out.emit()
        
        # Show login page
        self.show_login_page()
    
    def on_nav_clicked(self, page: str):
        """Handle navigation click"""
        if not self.current_user and page != "login":
            self.show_login_page()
            return
        
        if page == "dashboard":
            self.show_dashboard()
        elif page == "image":
            self.show_image_generation()
        elif page == "video":
            self.show_video_generation()
        elif page == "history":
            self.show_history()
        elif page == "credits":
            self.show_credits()
        elif page == "settings":
            self.show_settings()
    
    def show_login_page(self):
        """Show login page"""
        self.content_stack.setCurrentIndex(0)
        self.sidebar.set_active_item("")
    
    def show_dashboard(self):
        """Show dashboard page"""
        self.content_stack.setCurrentIndex(1)
        self.sidebar.set_active_item("dashboard")
        self.dashboard_page.refresh()
    
    def show_image_generation(self):
        """Show image generation page"""
        self.content_stack.setCurrentIndex(2)
        self.sidebar.set_active_item("image")
    
    def show_video_generation(self):
        """Show video generation page"""
        self.content_stack.setCurrentIndex(3)
        self.sidebar.set_active_item("video")
    
    def show_history(self):
        """Show history page"""
        self.content_stack.setCurrentIndex(4)
        self.sidebar.set_active_item("history")
        self.history_page.refresh()
    
    def show_credits(self):
        """Show credits page"""
        self.content_stack.setCurrentIndex(5)
        self.sidebar.set_active_item("credits")
        self.credits_page.refresh()
    
    def show_settings(self):
        """Show settings page"""
        self.content_stack.setCurrentIndex(6)
        self.sidebar.set_active_item("settings")
    
    def show_register(self):
        """Show registration dialog"""
        from .dialogs.register_dialog import RegisterDialog
        dialog = RegisterDialog(self)
        if dialog.exec():
            # Registration successful
            data = dialog.get_data()
            response = self.api_client.register(
                data["email"],
                data["password"],
                data.get("full_name", ""),
            )
            if response.success:
                self.on_login_success(response.data)
            else:
                QMessageBox.critical(
                    self,
                    "Registration Failed",
                    response.error or "Unknown error",
                )
    
    def refresh_data(self):
        """Refresh user data"""
        if not self.current_user:
            return
        
        # Get updated user info
        response = self.api_client.get_current_user()
        if response.success:
            user_data = response.data
            self.config.user_credits = user_data.get("credits", 0)
            self.config.save()
            
            # Update sidebar
            self.sidebar.set_user_info(
                user_data.get("email", ""),
                user_data.get("credits", 0),
            )
            
            # Emit signal
            self.credits_updated.emit(user_data.get("credits", 0))
    
    def closeEvent(self, event):
        """Handle window close"""
        self.config.save()
        event.accept()
