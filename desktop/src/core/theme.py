"""Theme management"""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette, QColor


class ThemeManager(QObject):
    """Manage application theme"""
    
    theme_changed = Signal(bool)  # True = dark, False = light
    
    # Color schemes
    DARK_COLORS = {
        "background": "#0f0f0f",
        "surface": "#1a1a1a",
        "surface_variant": "#252525",
        "primary": "#6366f1",
        "primary_variant": "#818cf8",
        "secondary": "#a855f7",
        "accent": "#22d3ee",
        "text_primary": "#ffffff",
        "text_secondary": "#a1a1aa",
        "text_disabled": "#71717a",
        "border": "#27272a",
        "error": "#ef4444",
        "success": "#22c55e",
        "warning": "#f59e0b",
    }
    
    LIGHT_COLORS = {
        "background": "#ffffff",
        "surface": "#f8fafc",
        "surface_variant": "#f1f5f9",
        "primary": "#4f46e5",
        "primary_variant": "#6366f1",
        "secondary": "#9333ea",
        "accent": "#06b6d4",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "text_disabled": "#94a3b8",
        "border": "#e2e8f0",
        "error": "#dc2626",
        "success": "#16a34a",
        "warning": "#d97706",
    }
    
    def __init__(self):
        super().__init__()
        self._is_dark = True
    
    @property
    def is_dark(self) -> bool:
        return self._is_dark
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self._is_dark = not self._is_dark
        self.theme_changed.emit(self._is_dark)
    
    def set_dark_mode(self, dark: bool):
        """Set dark mode"""
        self._is_dark = dark
        self.theme_changed.emit(dark)
    
    def get_colors(self) -> dict:
        """Get current color scheme"""
        return self.DARK_COLORS if self._is_dark else self.LIGHT_COLORS
    
    def get_color(self, name: str) -> str:
        """Get a specific color"""
        colors = self.get_colors()
        return colors.get(name, "#000000")
    
    def get_stylesheet(self) -> str:
        """Get application stylesheet"""
        c = self.get_colors()
        
        return f"""
        QMainWindow {{
            background-color: {c['background']};
        }}
        
        QWidget {{
            background-color: {c['background']};
            color: {c['text_primary']};
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        
        QPushButton {{
            background-color: {c['primary']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        
        QPushButton:hover {{
            background-color: {c['primary_variant']};
        }}
        
        QPushButton:pressed {{
            background-color: {c['primary']};
        }}
        
        QPushButton:disabled {{
            background-color: {c['surface_variant']};
            color: {c['text_disabled']};
        }}
        
        QPushButton.secondary {{
            background-color: {c['surface_variant']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
        }}
        
        QPushButton.secondary:hover {{
            background-color: {c['surface']};
        }}
        
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 10px;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {c['primary']};
        }}
        
        QComboBox {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 10px;
            min-width: 100px;
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            selection-background-color: {c['primary']};
        }}
        
        QSpinBox, QDoubleSpinBox {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 10px;
        }}
        
        QSlider::groove:horizontal {{
            height: 6px;
            background: {c['surface_variant']};
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            width: 18px;
            height: 18px;
            margin: -6px 0;
            background: {c['primary']};
            border-radius: 9px;
        }}
        
        QSlider::sub-page:horizontal {{
            background: {c['primary']};
            border-radius: 3px;
        }}
        
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background-color: {c['surface_variant']};
            text-align: center;
            color: {c['text_primary']};
        }}
        
        QProgressBar::chunk {{
            background-color: {c['primary']};
            border-radius: 4px;
        }}
        
        QScrollBar:vertical {{
            background: {c['surface']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {c['surface_variant']};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: {c['text_secondary']};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QTabWidget::pane {{
            border: none;
            background-color: {c['background']};
        }}
        
        QTabBar::tab {{
            background-color: transparent;
            color: {c['text_secondary']};
            padding: 12px 24px;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        
        QTabBar::tab:selected {{
            color: {c['text_primary']};
            border-bottom: 2px solid {c['primary']};
        }}
        
        QTabBar::tab:hover:!selected {{
            color: {c['text_primary']};
        }}
        
        QGroupBox {{
            border: 1px solid {c['border']};
            border-radius: 12px;
            margin-top: 16px;
            padding-top: 16px;
            font-weight: 600;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
            color: {c['text_primary']};
        }}
        
        QLabel {{
            color: {c['text_primary']};
        }}
        
        QLabel.secondary {{
            color: {c['text_secondary']};
        }}
        
        QMenu {{
            background-color: {c['surface']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 8px;
        }}
        
        QMenu::item {{
            padding: 8px 24px;
            border-radius: 4px;
        }}
        
        QMenu::item:selected {{
            background-color: {c['primary']};
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {c['border']};
            margin: 8px 0;
        }}
        
        QToolTip {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 8px;
        }}
        
        QFrame[frameShape="4"] {{  # HLine
            color: {c['border']};
        }}
        
        QListWidget {{
            background-color: {c['surface']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 8px;
        }}
        
        QListWidget::item {{
            padding: 12px;
            border-radius: 6px;
        }}
        
        QListWidget::item:selected {{
            background-color: {c['primary']};
        }}
        
        QListWidget::item:hover:!selected {{
            background-color: {c['surface_variant']};
        }}
        """
    
    def apply_theme(self, app: QApplication):
        """Apply theme to application"""
        app.setStyleSheet(self.get_stylesheet())
