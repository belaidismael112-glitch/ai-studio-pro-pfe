"""Login page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from api.client import get_api_client


class LoginPage(QWidget):
    """Login page"""
    
    login_success = Signal(dict)
    register_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.setup_ui()
    
    def setup_ui(self):
        """Setup login page UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Login card
        card = QFrame()
        card.setFixedWidth(420)
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 16px;
                padding: 40px;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        
        # Title
        title = QLabel("Welcome Back")
        title.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)
        
        subtitle = QLabel("Sign in to continue creating")
        subtitle.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)
        
        card_layout.addSpacing(20)
        
        # Email
        email_label = QLabel("Email")
        email_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        card_layout.addWidget(email_label)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        self.email_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px 16px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
            }
        """)
        card_layout.addWidget(self.email_input)
        
        # Password
        password_label = QLabel("Password")
        password_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        card_layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px 16px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
            }
        """)
        card_layout.addWidget(self.password_input)
        
        # Forgot password
        forgot_btn = QPushButton("Forgot password?")
        forgot_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6366f1;
                border: none;
                text-align: right;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #818cf8;
            }
        """)
        forgot_btn.clicked.connect(self.on_forgot_password)
        card_layout.addWidget(forgot_btn)
        
        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(48)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
            QPushButton:disabled {
                background-color: #3f3f46;
                color: #71717a;
            }
        """)
        self.login_btn.clicked.connect(self.on_login)
        card_layout.addWidget(self.login_btn)
        
        # Divider
        divider_layout = QHBoxLayout()
        divider_layout.setSpacing(16)
        
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("color: #27272a;")
        divider_layout.addWidget(line1, 1)
        
        or_label = QLabel("or")
        or_label.setStyleSheet("color: #71717a; font-size: 12px;")
        divider_layout.addWidget(or_label)
        
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color: #27272a;")
        divider_layout.addWidget(line2, 1)
        
        card_layout.addLayout(divider_layout)
        
        # Register link
        register_layout = QHBoxLayout()
        register_layout.setAlignment(Qt.AlignCenter)
        
        no_account = QLabel("Don't have an account?")
        no_account.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        register_layout.addWidget(no_account)
        
        register_btn = QPushButton("Sign up")
        register_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6366f1;
                border: none;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #818cf8;
            }
        """)
        register_btn.clicked.connect(self.register_requested.emit)
        register_layout.addWidget(register_btn)
        
        card_layout.addLayout(register_layout)
        
        layout.addWidget(card)
    
    def on_login(self):
        """Handle login button click"""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Error", "Please enter email and password")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        
        # Make API call
        response = self.api_client.login(email, password)
        
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        
        if response.success:
            self.login_success.emit(response.data)
            self.email_input.clear()
            self.password_input.clear()
        else:
            QMessageBox.critical(
                self,
                "Login Failed",
                response.error or "Invalid email or password",
            )
    
    def on_forgot_password(self):
        """Handle forgot password"""
        QMessageBox.information(
            self,
            "Forgot Password",
            "Please contact support to reset your password.",
        )
