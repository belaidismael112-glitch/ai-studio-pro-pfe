"""Dashboard page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from api.client import get_api_client


class StatCard(QFrame):
    """Statistics card"""
    
    def __init__(self, icon: str, value: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 32px; color: {color};")
        layout.addWidget(icon_label)
        
        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        layout.addWidget(value_label)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        layout.addWidget(label_widget)
        
        self.value_label = value_label
    
    def set_value(self, value: str):
        """Update value"""
        self.value_label.setText(value)


class QuickActionCard(QFrame):
    """Quick action card"""
    
    clicked = None  # Will be connected externally
    
    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 24px;
            }
            QFrame:hover {
                border: 1px solid #6366f1;
                background-color: #252525;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 40px;")
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 18px;
            font-weight: 600;
        """)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)


class DashboardPage(QWidget):
    """Dashboard page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dashboard UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(32)
        
        # Header
        header = QLabel("Dashboard")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 32px;
            font-weight: 700;
        """)
        layout.addWidget(header)
        
        # Stats section
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.total_card = StatCard("🎨", "0", "Total Generations", "#6366f1")
        self.image_card = StatCard("🖼️", "0", "Images Generated", "#22d3ee")
        self.video_card = StatCard("🎬", "0", "Videos Generated", "#a855f7")
        self.credits_card = StatCard("💎", "0", "Credits Available", "#22c55e")
        
        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.image_card)
        stats_layout.addWidget(self.video_card)
        stats_layout.addWidget(self.credits_card)
        
        layout.addLayout(stats_layout)
        
        # Quick actions section
        actions_header = QLabel("Quick Actions")
        actions_header.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin-top: 20px;
        """)
        layout.addWidget(actions_header)
        
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(20)
        
        self.image_action = QuickActionCard(
            "🖼️",
            "Generate Image",
            "Create stunning AI images from text descriptions",
        )
        
        self.video_action = QuickActionCard(
            "🎬",
            "Generate Video",
            "Transform your ideas into AI-generated videos",
        )
        
        self.history_action = QuickActionCard(
            "📜",
            "View History",
            "Browse and manage your previous generations",
        )
        
        self.credits_action = QuickActionCard(
            "💎",
            "Buy Credits",
            "Purchase more credits to continue creating",
        )
        
        actions_layout.addWidget(self.image_action)
        actions_layout.addWidget(self.video_action)
        actions_layout.addWidget(self.history_action)
        actions_layout.addWidget(self.credits_action)
        
        layout.addLayout(actions_layout)
        
        # Recent activity section
        activity_header = QLabel("Recent Activity")
        activity_header.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin-top: 20px;
        """)
        layout.addWidget(activity_header)
        
        self.activity_frame = QFrame()
        self.activity_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        activity_layout = QVBoxLayout(self.activity_frame)
        
        self.activity_placeholder = QLabel("No recent activity")
        self.activity_placeholder.setStyleSheet("color: #71717a; font-size: 14px;")
        self.activity_placeholder.setAlignment(Qt.AlignCenter)
        activity_layout.addWidget(self.activity_placeholder)
        
        layout.addWidget(self.activity_frame)
        layout.addStretch()
    
    def refresh(self):
        """Refresh dashboard data"""
        # Get user stats
        response = self.api_client.get_user_stats()
        if response.success:
            stats = response.data
            self.total_card.set_value(str(stats.get("total_generations", 0)))
            self.image_card.set_value(str(stats.get("image_generations", 0)))
            self.video_card.set_value(str(stats.get("video_generations", 0)))
        
        # Get credit balance
        credit_response = self.api_client.get_credit_balance()
        if credit_response.success:
            credits = credit_response.data.get("credits", 0)
            self.credits_card.set_value(str(credits))
