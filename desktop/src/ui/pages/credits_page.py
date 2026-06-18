"""Credits page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from api.client import get_api_client


class CreditPackageCard(QFrame):
    """Credit package card"""
    
    def __init__(self, package: dict, parent=None):
        super().__init__(parent)
        self.package = package
        self.setup_ui()
    
    def setup_ui(self):
        self.setFixedWidth(280)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #27272a;
                border-radius: 16px;
                padding: 24px;
            }
            QFrame:hover {
                border: 2px solid #6366f1;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Package name
        name = QLabel(self.package.get("name", ""))
        name.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 700;
        """)
        layout.addWidget(name)
        
        # Credits
        credits = self.package.get("credits", 0)
        credits_label = QLabel(f"💎 {credits:,} credits")
        credits_label.setStyleSheet("color: #22d3ee; font-size: 24px; font-weight: 600;")
        layout.addWidget(credits_label)
        
        # Description
        desc = self.package.get("description", "")
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #a1a1aa; font-size: 13px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # Price
        price = self.package.get("price", 0)
        currency = self.package.get("currency", "eur").upper()
        price_label = QLabel(f"€{price:.2f}")
        price_label.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        layout.addWidget(price_label)
        
        # Buy button
        self.buy_btn = QPushButton("Purchase")
        self.buy_btn.setFixedHeight(44)
        self.buy_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
        """)
        layout.addWidget(self.buy_btn)


class CreditsPage(QWidget):
    """Credits page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.packages = []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup credits page UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(32)
        
        # Header
        header = QLabel("Credits & Billing")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        layout.addWidget(header)
        
        # Balance card
        balance_card = QFrame()
        balance_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #6366f1,
                    stop: 1 #a855f7
                );
                border-radius: 16px;
                padding: 32px;
            }
        """)
        
        balance_layout = QHBoxLayout(balance_card)
        
        balance_info = QVBoxLayout()
        
        balance_label = QLabel("Your Balance")
        balance_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
        balance_info.addWidget(balance_label)
        
        self.balance_value = QLabel("0")
        self.balance_value.setStyleSheet("color: white; font-size: 48px; font-weight: 700;")
        balance_info.addWidget(self.balance_value)
        
        credits_text = QLabel("credits available")
        credits_text.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
        balance_info.addWidget(credits_text)
        
        balance_layout.addLayout(balance_info)
        balance_layout.addStretch()
        
        layout.addWidget(balance_card)
        
        # Packages section
        packages_header = QLabel("Purchase Credits")
        packages_header.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin-top: 20px;
        """)
        layout.addWidget(packages_header)
        
        self.packages_layout = QHBoxLayout()
        self.packages_layout.setSpacing(20)
        self.packages_layout.addStretch()
        
        layout.addLayout(self.packages_layout)
        
        # Transaction history
        history_header = QLabel("Transaction History")
        history_header.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin-top: 20px;
        """)
        layout.addWidget(history_header)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Date", "Type", "Amount", "Balance"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                color: #ffffff;
                gridline-color: #27272a;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #ffffff;
                padding: 12px;
                border: none;
                font-weight: 600;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #27272a;
            }
        """)
        self.history_table.setMaximumHeight(300)
        layout.addWidget(self.history_table)
        
        layout.addStretch()
    
    def refresh(self):
        """Refresh credits data"""
        # Get balance
        balance_response = self.api_client.get_credit_balance()
        if balance_response.success:
            credits = balance_response.data.get("credits", 0)
            self.balance_value.setText(f"{credits:,}")
        
        # Get packages
        packages_response = self.api_client.get_credit_packages()
        if packages_response.success:
            self.packages = packages_response.data
            self.display_packages()
        
        # Get transaction history
        history_response = self.api_client.get_credit_history(limit=20)
        if history_response.success:
            self.display_history(history_response.data)
    
    def display_packages(self):
        """Display credit packages"""
        # Clear existing
        while self.packages_layout.count() > 1:
            item = self.packages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for package in self.packages:
            card = CreditPackageCard(package)
            card.buy_btn.clicked.connect(
                lambda checked, p=package: self.on_purchase(p)
            )
            self.packages_layout.insertWidget(
                self.packages_layout.count() - 1, card
            )
    
    def display_history(self, transactions: list):
        """Display transaction history"""
        self.history_table.setRowCount(len(transactions))
        
        for i, tx in enumerate(transactions):
            # Date
            date = tx.get("created_at", "")
            if date:
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            self.history_table.setItem(i, 0, QTableWidgetItem(date))
            
            # Type
            tx_type = tx.get("transaction_type", "")
            type_item = QTableWidgetItem(tx_type.capitalize())
            self.history_table.setItem(i, 1, type_item)
            
            # Amount
            amount = tx.get("amount", 0)
            amount_str = f"+{amount}" if amount > 0 else str(amount)
            amount_item = QTableWidgetItem(amount_str)
            if amount > 0:
                amount_item.setForeground(Qt.green)
            else:
                amount_item.setForeground(Qt.red)
            self.history_table.setItem(i, 2, amount_item)
            
            # Balance
            balance = tx.get("balance_after", 0)
            self.history_table.setItem(i, 3, QTableWidgetItem(str(balance)))
    
    def on_purchase(self, package: dict):
        """Handle purchase button click"""
        package_id = package.get("id")
        
        response = self.api_client.purchase_credits(package_id)
        
        if response.success:
            import webbrowser
            checkout_url = response.data.get("checkout_url")
            if checkout_url:
                webbrowser.open(checkout_url)
        else:
            QMessageBox.critical(
                self,
                "Purchase Failed",
                response.error or "Failed to create checkout session",
            )
