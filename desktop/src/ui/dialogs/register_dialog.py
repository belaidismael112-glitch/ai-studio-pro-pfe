"""Register dialog"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt


class RegisterDialog(QDialog):
    """Registration dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Account")
        self.setFixedWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
            }
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
            QPushButton.secondary {
                background-color: transparent;
                color: #a1a1aa;
                border: 1px solid #3f3f46;
            }
            QPushButton.secondary:hover {
                background-color: #252525;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Create Your Account")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Start creating with AI today")
        subtitle.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(16)
        
        # Full name
        name_label = QLabel("Full Name (optional)")
        layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("John Doe")
        layout.addWidget(self.name_input)
        
        # Email
        email_label = QLabel("Email *")
        layout.addWidget(email_label)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        layout.addWidget(self.email_input)
        
        # Password
        password_label = QLabel("Password *")
        layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("At least 8 characters")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        
        # Confirm password
        confirm_label = QLabel("Confirm Password *")
        layout.addWidget(confirm_label)
        
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Repeat your password")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.confirm_input)
        
        layout.addSpacing(16)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        register_btn = QPushButton("Create Account")
        register_btn.clicked.connect(self.on_register)
        btn_layout.addWidget(register_btn)
        
        layout.addLayout(btn_layout)
    
    def on_register(self):
        """Handle register button"""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Error", "Please fill in all required fields")
            return
        
        if len(password) < 8:
            QMessageBox.warning(self, "Error", "Password must be at least 8 characters")
            return
        
        if password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
        
        self.accept()
    
    def get_data(self) -> dict:
        """Get registration data"""
        return {
            "full_name": self.name_input.text().strip(),
            "email": self.email_input.text().strip(),
            "password": self.password_input.text(),
        }
