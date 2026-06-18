"""History page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QMessageBox,
    QComboBox, QScrollArea, QGridLayout,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import httpx
from datetime import datetime

from api.client import get_api_client


class HistoryLoader(QThread):
    """Worker to load history"""
    
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        try:
            response = self.api_client.list_generations(page_size=50)
            if response.success:
                self.finished.emit(response.data.get("items", []))
            else:
                self.error.emit(response.error or "Failed to load history")
        except Exception as e:
            self.error.emit(str(e))


class HistoryItem(QFrame):
    """History item widget"""
    
    def __init__(self, generation: dict, parent=None):
        super().__init__(parent)
        self.generation = generation
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame:hover {
                border: 1px solid #6366f1;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(16)
        
        # Type icon
        gen_type = self.generation.get("generation_type", "image")
        icon = "🖼️" if gen_type == "image" else "🎬"
        
        type_label = QLabel(icon)
        type_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(type_label)
        
        # Info
        info_layout = QVBoxLayout()
        
        # Prompt (truncated)
        prompt = self.generation.get("prompt", "")
        if len(prompt) > 60:
            prompt = prompt[:57] + "..."
        
        prompt_label = QLabel(prompt)
        prompt_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        prompt_label.setWordWrap(True)
        info_layout.addWidget(prompt_label)
        
        # Meta info
        meta_parts = []
        
        status = self.generation.get("status", "unknown")
        status_colors = {
            "completed": "#22c55e",
            "pending": "#f59e0b",
            "processing": "#6366f1",
            "failed": "#ef4444",
        }
        status_color = status_colors.get(status, "#71717a")
        meta_parts.append(f"<span style='color: {status_color}'>{status.upper()}</span>")
        
        width = self.generation.get("width")
        height = self.generation.get("height")
        if width and height:
            meta_parts.append(f"{width}x{height}")
        
        duration = self.generation.get("duration")
        if duration:
            meta_parts.append(f"{duration}s")
        
        credits = self.generation.get("credits_used", 0)
        meta_parts.append(f"💎 {credits}")
        
        created = self.generation.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                meta_parts.append(dt.strftime("%Y-%m-%d %H:%M"))
            except:
                pass
        
        meta_label = QLabel(" | ".join(meta_parts))
        meta_label.setStyleSheet("color: #71717a; font-size: 12px;")
        info_layout.addWidget(meta_label)
        
        layout.addLayout(info_layout, 1)
        
        # Actions
        if self.generation.get("result_url"):
            download_btn = QPushButton("Download")
            download_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6366f1;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #818cf8;
                }
            """)
            download_btn.clicked.connect(self.download)
            layout.addWidget(download_btn)


class HistoryPage(QWidget):
    """History page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.generations = []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup history page UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("Generation History")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        """)
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        # Filter
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #a1a1aa;")
        header_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Images", "Videos", "Completed", "Failed"])
        self.filter_combo.setFixedWidth(120)
        self.filter_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 8px;
                color: #ffffff;
            }
        """)
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        header_layout.addWidget(self.filter_combo)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Scroll area for history items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setSpacing(12)
        self.history_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.history_container)
        layout.addWidget(scroll)
        
        # Loading label
        self.loading_label = QLabel("Loading...")
        self.loading_label.setStyleSheet("color: #a1a1aa; font-size: 16px;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)
    
    def refresh(self):
        """Refresh history"""
        self.loading_label.show()
        
        # Clear existing items
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Load history
        self.loader = HistoryLoader(self.api_client)
        self.loader.finished.connect(self.on_history_loaded)
        self.loader.error.connect(self.on_history_error)
        self.loader.start()
    
    def on_history_loaded(self, generations: list):
        """Handle loaded history"""
        self.loading_label.hide()
        self.generations = generations
        self.display_generations(generations)
    
    def on_history_error(self, error: str):
        """Handle history load error"""
        self.loading_label.hide()
        QMessageBox.critical(self, "Error", f"Failed to load history: {error}")
    
    def display_generations(self, generations: list):
        """Display generation items"""
        if not generations:
            empty_label = QLabel("No generations yet. Start creating!")
            empty_label.setStyleSheet("color: #71717a; font-size: 16px; padding: 40px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.history_layout.addWidget(empty_label)
            return
        
        for gen in generations:
            item = HistoryItem(gen)
            self.history_layout.addWidget(item)
    
    def apply_filter(self, filter_text: str):
        """Apply filter to history"""
        filter_lower = filter_text.lower()
        
        filtered = self.generations
        
        if filter_lower == "images":
            filtered = [g for g in self.generations if g.get("generation_type") == "image"]
        elif filter_lower == "videos":
            filtered = [g for g in self.generations if g.get("generation_type") == "video"]
        elif filter_lower == "completed":
            filtered = [g for g in self.generations if g.get("status") == "completed"]
        elif filter_lower == "failed":
            filtered = [g for g in self.generations if g.get("status") == "failed"]
        
        # Clear and redisplay
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.display_generations(filtered)
