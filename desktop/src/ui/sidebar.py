"""Sidebar navigation component"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class NavButton(QPushButton):
    """Navigation button"""
    
    def __init__(self, icon: str, text: str, page: str, parent=None):
        super().__init__(parent)
        self.page = page
        self.setText(f"  {icon}  {text}")
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a1a1aa;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #252525;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #6366f1;
                color: #ffffff;
            }
        """)
        self.setCheckable(True)


class Sidebar(QFrame):
    """Application sidebar"""
    
    nav_clicked = Signal(str)
    logout_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup sidebar UI"""
        self.setFixedWidth(260)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-right: 1px solid #27272a;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)
        
        # Logo
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("✨")
        logo_icon.setStyleSheet("font-size: 24px;")
        logo_layout.addWidget(logo_icon)
        
        logo_text = QLabel("AI Studio Pro")
        logo_text.setStyleSheet("""
            color: #ffffff;
            font-size: 18px;
            font-weight: 700;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        
        layout.addLayout(logo_layout)
        layout.addSpacing(32)
        
        # Navigation buttons
        self.nav_buttons = []
        
        nav_items = [
            ("🏠", "Dashboard", "dashboard"),
            ("🖼️", "Image Generation", "image"),
            ("🎬", "Video Generation", "video"),
            ("📜", "History", "history"),
            ("💎", "Credits", "credits"),
            ("⚙️", "Settings", "settings"),
        ]
        
        for icon, text, page in nav_items:
            btn = NavButton(icon, text, page)
            btn.clicked.connect(lambda checked, p=page: self.on_nav_clicked(p))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # User section
        self.user_frame = QFrame()
        self.user_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        
        user_layout = QVBoxLayout(self.user_frame)
        user_layout.setContentsMargins(12, 12, 12, 12)
        user_layout.setSpacing(8)
        
        # User email
        self.user_email_label = QLabel("Not logged in")
        self.user_email_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        self.user_email_label.setWordWrap(True)
        user_layout.addWidget(self.user_email_label)
        
        # Credits
        self.credits_label = QLabel("💎 0 credits")
        self.credits_label.setStyleSheet("color: #22d3ee; font-size: 13px; font-weight: 600;")
        user_layout.addWidget(self.credits_label)
        
        # Logout button
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ef4444;
                border: 1px solid #ef4444;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.logout_btn.clicked.connect(self.logout_clicked.emit)
        user_layout.addWidget(self.logout_btn)
        
        self.user_frame.hide()
        layout.addWidget(self.user_frame)
        
        # Login button (shown when not logged in)
        self.login_btn = QPushButton("Login / Register")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
        """)
        self.login_btn.clicked.connect(lambda: self.nav_clicked.emit("login"))
        layout.addWidget(self.login_btn)
    
    def on_nav_clicked(self, page: str):
        """Handle navigation click"""
        self.set_active_item(page)
        self.nav_clicked.emit(page)
    
    def set_active_item(self, page: str):
        """Set active navigation item"""
        for btn in self.nav_buttons:
            btn.setChecked(btn.page == page)
    
    def set_user_info(self, email: str, credits: int):
        """Update user info display"""
        self.user_email_label.setText(email)
        self.credits_label.setText(f"💎 {credits:,} credits")
    
    def show_logged_in(self, logged_in: bool):
        """Show/hide user section based on login status"""
        if logged_in:
            self.user_frame.show()
            self.login_btn.hide()
        else:
            self.user_frame.hide()
            self.login_btn.show()
            self.user_email_label.setText("Not logged in")
            self.credits_label.setText("💎 0 credits")
