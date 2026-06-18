"""Image generation page"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QSpinBox, QSlider,
    QProgressBar, QMessageBox, QFileDialog, QTextEdit,
    QGroupBox, QGridLayout, QTabWidget, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import httpx
import time
from pathlib import Path

from api.client import get_api_client
from core.config import AppConfig



class GenerationStatusPoller(QThread):
    """Poll generation status in background until it completes."""

    updated = Signal(dict)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, api_client, generation_id: int, poll_interval: float = 2.0):
        super().__init__()
        self.api_client = api_client
        self.generation_id = generation_id
        self.poll_interval = poll_interval
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            while not self._stop:
                resp = self.api_client.get_generation(self.generation_id)
                if not resp.success:
                    self.error.emit(resp.error or "Failed to fetch generation")
                    return
                data = resp.data
                self.updated.emit(data)
                status = (data.get("status") or "").lower()
                if status in {"completed", "failed"}:
                    self.done.emit(data)
                    return
                time.sleep(self.poll_interval)
        except Exception as e:
            self.error.emit(str(e))


class ImageGenerationWorker(QThread):
    """Worker thread for image generation"""
    
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, api_client, params: dict, mode: str = "text2img"):
        super().__init__()
        self.api_client = api_client
        self.params = params
        self.mode = mode
    
    def run(self):
        """Run generation"""
        try:
            if self.mode == "img2img":
                response = self.api_client.generate_image_img2img(**self.params)
            else:
                response = self.api_client.generate_image(**self.params)
            if response.success:
                self.finished.emit(response.data)
            else:
                self.error.emit(response.error or "Generation failed")
        except Exception as e:
            self.error.emit(str(e))


class ImageGenerationPage(QWidget):
    """Image generation page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.config = AppConfig.load()
        self.current_generation = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup image generation UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(32)
        
        # Left panel - Controls
        left_panel = QFrame()
        left_panel.setFixedWidth(450)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(20)
        
        # Header
        header = QLabel("Image Generation")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 24px;
            font-weight: 700;
        """)
        left_layout.addWidget(header)
        
        subtitle = QLabel("Create stunning AI images from text descriptions")
        subtitle.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        subtitle.setWordWrap(True)
        left_layout.addWidget(subtitle)

        # Status badge
        self.status_badge = QLabel("Idle")
        self.status_badge.setStyleSheet("""
            QLabel {
                background-color: #252525;
                color: #a1a1aa;
                border: 1px solid #3f3f46;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
                max-width: 140px;
            }
        """)
        left_layout.addWidget(self.status_badge, alignment=Qt.AlignLeft)

        
        left_layout.addSpacing(10)
        
        # Tabs
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #252525;
                color: #a1a1aa;
                padding: 10px 14px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }
            QTabBar::tab:selected { background: #2d2d2d; color: #ffffff; }
        """)

        # --- Tab 1: Text → Image ---
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        text_layout.setSpacing(16)
        text_layout.setContentsMargins(0, 16, 0, 0)

        prompt_label = QLabel("Prompt *")
        prompt_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        text_layout.addWidget(prompt_label)

        self.txt_prompt_input = QTextEdit()
        self.txt_prompt_input.setPlaceholderText("Describe the image you want to create...")
        self.txt_prompt_input.setFixedHeight(100)
        self.txt_prompt_input.setStyleSheet("""
            QTextEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 14px;
            }
            QTextEdit:focus { border: 2px solid #6366f1; }
        """)
        text_layout.addWidget(self.txt_prompt_input)

        neg_label = QLabel("Negative Prompt (optional)")
        neg_label.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        text_layout.addWidget(neg_label)

        self.txt_negative_input = QLineEdit()
        self.txt_negative_input.setPlaceholderText("Things to avoid in the image...")
        self.txt_negative_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus { border: 2px solid #6366f1; }
        """)
        text_layout.addWidget(self.txt_negative_input)

        style_label = QLabel("Style")
        style_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        text_layout.addWidget(style_label)

        self.txt_style_combo = QComboBox()
        self.txt_style_combo.addItems([
            "Default",
            "Photorealistic",
            "Digital Art",
            "Anime",
            "Oil Painting",
            "Watercolor",
            "Sketch",
            "Cinematic",
            "Neonpunk",
            "Fantasy",
            "3D Render",
        ])
        self.txt_style_combo.setStyleSheet("""
            QComboBox {
                background-color: #252525;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 14px;
            }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox QAbstractItemView {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #27272a;
                border-radius: 8px;
                selection-background-color: #6366f1;
            }
        """)
        text_layout.addWidget(self.txt_style_combo)

        size_layout = QHBoxLayout()
        size_label = QLabel("Size:")
        size_label.setStyleSheet("color: #ffffff; font-size: 14px;")
        size_layout.addWidget(size_label)

        self.txt_size_combo = QComboBox()
        self.txt_size_combo.addItems([
            "512x512",
            "768x768",
            "1024x1024",
            "1024x576 (Landscape)",
            "576x1024 (Portrait)",
            "1280x720",
            "1920x1080",
        ])
        self.txt_size_combo.setCurrentText("1024x1024")
        size_layout.addWidget(self.txt_size_combo)
        size_layout.addStretch()
        text_layout.addLayout(size_layout)

        self.txt_cost_label = QLabel("💎 Cost: 10 credits per image")
        self.txt_cost_label.setStyleSheet("color: #22d3ee; font-size: 13px;")
        text_layout.addWidget(self.txt_cost_label)

        self.txt_generate_btn = QPushButton("Generate Image")
        self.txt_generate_btn.setFixedHeight(48)
        self.txt_generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #818cf8; }
            QPushButton:disabled { background-color: #3f3f46; color: #71717a; }
        """)
        self.txt_generate_btn.clicked.connect(self.on_generate)
        text_layout.addWidget(self.txt_generate_btn)

        # --- Tab 2: Image → Image ---
        img_tab = QWidget()
        img_layout = QVBoxLayout(img_tab)
        img_layout.setSpacing(16)
        img_layout.setContentsMargins(0, 16, 0, 0)

        self.input_image_path: str | None = None
        upload_row = QHBoxLayout()
        self.upload_btn = QPushButton("⬆️ Upload Image")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #3f3f46; }
        """)
        self.upload_btn.clicked.connect(self.on_upload_image)
        upload_row.addWidget(self.upload_btn)
        self.upload_path_label = QLabel("No image selected")
        self.upload_path_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        upload_row.addWidget(self.upload_path_label, 1)
        img_layout.addLayout(upload_row)

        strength_row = QHBoxLayout()
        strength_label = QLabel("Strength")
        strength_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        strength_row.addWidget(strength_label)
        self.strength_value = QLabel("0.65")
        self.strength_value.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        strength_row.addStretch()
        strength_row.addWidget(self.strength_value)
        img_layout.addLayout(strength_row)

        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(10, 90)
        self.strength_slider.setValue(65)
        self.strength_slider.valueChanged.connect(lambda v: self.strength_value.setText(f"{v/100:.2f}"))
        img_layout.addWidget(self.strength_slider)

        img_prompt_label = QLabel("Prompt")
        img_prompt_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        img_layout.addWidget(img_prompt_label)

        self.img_prompt_input = QTextEdit()
        self.img_prompt_input.setPlaceholderText("Describe how you want to transform the image...")
        self.img_prompt_input.setFixedHeight(90)
        self.img_prompt_input.setStyleSheet(self.txt_prompt_input.styleSheet())
        img_layout.addWidget(self.img_prompt_input)

        img_neg_label = QLabel("Negative Prompt (optional)")
        img_neg_label.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        img_layout.addWidget(img_neg_label)

        self.img_negative_input = QLineEdit()
        self.img_negative_input.setPlaceholderText("Things to avoid in the image...")
        self.img_negative_input.setStyleSheet(self.txt_negative_input.styleSheet())
        img_layout.addWidget(self.img_negative_input)

        img_style_label = QLabel("Style")
        img_style_label.setStyleSheet(style_label.styleSheet())
        img_layout.addWidget(img_style_label)
        self.img_style_combo = QComboBox()
        self.img_style_combo.addItems(self.txt_style_combo.itemText(i) for i in range(self.txt_style_combo.count()))
        self.img_style_combo.setStyleSheet(self.txt_style_combo.styleSheet())
        img_layout.addWidget(self.img_style_combo)

        img_size_layout = QHBoxLayout()
        img_size_label = QLabel("Size:")
        img_size_label.setStyleSheet(size_label.styleSheet())
        img_size_layout.addWidget(img_size_label)
        self.img_size_combo = QComboBox()
        self.img_size_combo.addItems(self.txt_size_combo.itemText(i) for i in range(self.txt_size_combo.count()))
        self.img_size_combo.setCurrentText("1024x1024")
        img_size_layout.addWidget(self.img_size_combo)
        img_size_layout.addStretch()
        img_layout.addLayout(img_size_layout)

        self.img_cost_label = QLabel("💎 Cost: 12 credits per image (img2img)")
        self.img_cost_label.setStyleSheet("color: #22d3ee; font-size: 13px;")
        img_layout.addWidget(self.img_cost_label)

        self.img_generate_btn = QPushButton("Generate (Image → Image)")
        self.img_generate_btn.setFixedHeight(48)
        self.img_generate_btn.setStyleSheet(self.txt_generate_btn.styleSheet())
        self.img_generate_btn.clicked.connect(self.on_generate)
        img_layout.addWidget(self.img_generate_btn)

        self.mode_tabs.addTab(text_tab, "Text → Image")
        self.mode_tabs.addTab(img_tab, "Image → Image")
        left_layout.addWidget(self.mode_tabs)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #252525;
                height: 4px;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 4px;
            }
        """)
        self.progress.hide()
        left_layout.addWidget(self.progress)
        
        left_layout.addStretch()
        
        layout.addWidget(left_panel)
        
        # Right panel - Preview
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        
        right_layout = QVBoxLayout(right_panel)
        
        # Preview / History tabs
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #252525;
                color: #a1a1aa;
                padding: 8px 12px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }
            QTabBar::tab:selected { background: #2d2d2d; color: #ffffff; }
        """)

        # --- Preview tab (Input vs Output) ---
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(0, 12, 0, 0)
        preview_layout.setSpacing(12)

        header_row = QHBoxLayout()
        preview_header = QLabel("Preview")
        preview_header.setStyleSheet("""
            color: #ffffff;
            font-size: 18px;
            font-weight: 600;
        """)
        header_row.addWidget(preview_header)
        header_row.addStretch()
        preview_layout.addLayout(header_row)

        io_layout = QHBoxLayout()
        io_layout.setSpacing(12)

        def _make_preview_card(title: str):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #252525;
                    border: 1px solid #3f3f46;
                    border-radius: 12px;
                }
            """)
            v = QVBoxLayout(card)
            v.setContentsMargins(10, 10, 10, 10)
            v.setSpacing(8)
            t = QLabel(title)
            t.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
            v.addWidget(t)
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #1f1f1f;
                    border: 2px dashed #3f3f46;
                    border-radius: 10px;
                    color: #71717a;
                    font-size: 13px;
                }
            """)
            lbl.setMinimumSize(260, 260)
            v.addWidget(lbl, 1)
            return card, lbl

        input_card, self.input_preview_label = _make_preview_card("Input")
        output_card, self.output_preview_label = _make_preview_card("Output")

        self.input_preview_label.setText("No input")
        self.output_preview_label.setText("Your generated image\nwill appear here")

        io_layout.addWidget(input_card, 1)
        io_layout.addWidget(output_card, 1)
        preview_layout.addLayout(io_layout, 1)

        self.preview_tabs.addTab(preview_tab, "Preview")

        # --- History tab ---
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(0, 12, 0, 0)
        history_layout.setSpacing(10)

        history_header_row = QHBoxLayout()
        history_header = QLabel("History")
        history_header.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 600;")
        history_header_row.addWidget(history_header)
        history_header_row.addStretch()

        self.history_refresh_btn = QPushButton("↻ Refresh")
        self.history_refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3f3f46; }
        """)
        self.history_refresh_btn.clicked.connect(self.refresh_history)
        history_header_row.addWidget(self.history_refresh_btn)
        history_layout.addLayout(history_header_row)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: 1px solid #3f3f46;
                border-radius: 12px;
                padding: 6px;
                color: #e5e7eb;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background-color: #3b3b3b;
            }
        """)
        self.history_list.itemClicked.connect(self.on_history_item_clicked)
        history_layout.addWidget(self.history_list, 1)

        self.preview_tabs.addTab(history_tab, "History")

        right_layout.addWidget(self.preview_tabs, 1)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("💾 Download")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:disabled {
                background-color: #3f3f46;
                color: #71717a;
            }
        """)
        self.download_btn.clicked.connect(self.on_download)
        action_layout.addWidget(self.download_btn)
        
        self.regenerate_btn = QPushButton("🔄 Regenerate")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        self.regenerate_btn.clicked.connect(self.on_generate)
        action_layout.addWidget(self.regenerate_btn)
        
        action_layout.addStretch()
        right_layout.addLayout(action_layout)
        
        layout.addWidget(right_panel, 1)
    
    def _set_status_badge(self, label: str):
        """Update the small status badge."""
        label_l = (label or "").lower()
        if label_l in {"queued", "pending"}:
            bg, fg, border = "#1d4ed8", "#ffffff", "#1e40af"
            txt = "Queued"
        elif label_l in {"processing", "running"}:
            bg, fg, border = "#a855f7", "#ffffff", "#7e22ce"
            txt = "Processing"
        elif label_l in {"completed", "done"}:
            bg, fg, border = "#22c55e", "#ffffff", "#16a34a"
            txt = "Done"
        elif label_l in {"failed", "error"}:
            bg, fg, border = "#ef4444", "#ffffff", "#b91c1c"
            txt = "Failed"
        else:
            bg, fg, border = "#252525", "#a1a1aa", "#3f3f46"
            txt = label or "Idle"
        self.status_badge.setText(txt)
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
                max-width: 140px;
            }}
        """)

    def _start_polling(self, generation_id: int):
        """Start polling a queued generation until it completes."""
        if getattr(self, "poller", None):
            try: self.poller.stop()
            except Exception: pass
        self.poller = GenerationStatusPoller(self.api_client, generation_id)
        self.poller.updated.connect(self.on_poll_update)
        self.poller.done.connect(self.on_poll_done)
        self.poller.error.connect(self.on_generation_error)
        self.poller.start()

    def on_poll_update(self, data: dict):
        status = (data.get("status") or "").lower()
        if status in {"processing", "running"}:
            self._set_status_badge("processing")
        elif status in {"queued", "pending"}:
            self._set_status_badge("queued")

    def on_poll_done(self, data: dict):
        self.current_generation = data
        status = (data.get("status") or "").lower()
        self.progress.hide()
        self.txt_generate_btn.setEnabled(True)
        self.img_generate_btn.setEnabled(True)
        self.txt_generate_btn.setText("Generate Image")
        self.img_generate_btn.setText("Generate (Image → Image)")
        if status == "completed":
            self._set_status_badge("completed")
            self.download_btn.setEnabled(True)
            self.regenerate_btn.setEnabled(True)
            self._try_show_output_image(data.get("result_url"))
        else:
            self._set_status_badge("failed")
            QMessageBox.warning(self, "Error", data.get("error_message") or "Generation failed")
        self.refresh_history()

    def refresh_history(self):
        """Reload recent generations into the History tab."""
        try:
            resp = self.api_client.list_generations(page=1, page_size=30)
            if not resp.success:
                return
            items = resp.data.get("items", []) if isinstance(resp.data, dict) else (resp.data or [])
            items = [g for g in items if g.get("generation_type") in {"image", "img2img"}]
            self.history_list.clear()
            for g in items:
                gid = g.get("id")
                st = (g.get("status") or "").capitalize()
                pr = (g.get("prompt") or "").strip().replace("\n", " ")
                if len(pr) > 60: pr = pr[:60] + "…"
                it = QListWidgetItem(f"#{gid} · {st} · {pr}")
                it.setData(Qt.UserRole, g)
                self.history_list.addItem(it)
        except Exception:
            pass

    def on_history_item_clicked(self, item: QListWidgetItem):
        g = item.data(Qt.UserRole) or {}
        gid = g.get("id")
        if not gid: return
        try:
            resp = self.api_client.get_generation(int(gid))
            if not resp.success: return
            data = resp.data
            self._set_status_badge(data.get("status") or "")
            self.input_preview_label.setText("Input not available")
            self.input_preview_label.setPixmap(QPixmap())
            self._try_show_output_image(data.get("result_url"))
            self.current_generation = data
            self.download_btn.setEnabled(bool(data.get("result_url")))
            self.preview_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def _try_show_output_image(self, result_url):
        if not result_url:
            return
        try:
            response = httpx.get(result_url)
            image = QImage.fromData(response.content)
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(self.output_preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.output_preview_label.setPixmap(scaled)
            self.output_preview_label.setStyleSheet("""
                QLabel {
                    background-color: #1f1f1f;
                    border: 2px solid #6366f1;
                    border-radius: 10px;
                }
            """)
            self.preview_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def on_generate(self):
        """Handle generate button click (Text→Image or Image→Image)."""

        tab = self.mode_tabs.currentIndex()

        def _parse_size(size_text: str) -> tuple[int, int]:
            size_part = size_text.split(" ")[0]
            if "x" in size_part:
                w, h = size_part.lower().split("x")[:2]
                return int(w), int(h)
            return 1024, 1024

        if tab == 0:
            # Text → Image
            prompt = self.txt_prompt_input.toPlainText().strip()
            if not prompt:
                QMessageBox.warning(self, "Error", "Please enter a prompt")
                return

            width, height = _parse_size(self.txt_size_combo.currentText())
            style = self.txt_style_combo.currentText().lower().replace(" ", "_")
            if style == "default":
                style = None
            elif style == "3d_render":
                style = "3d"

            params = {
                "prompt": prompt,
                "negative_prompt": self.txt_negative_input.text(),
                "width": width,
                "height": height,
                "style": style,
            }
            self._active_btn = self.txt_generate_btn
            self.worker = ImageGenerationWorker(self.api_client, params, mode="text2img")

        else:
            # Image → Image
            if not getattr(self, "input_image_path", None):
                QMessageBox.warning(self, "Error", "Please upload an input image")
                return

            prompt = self.img_prompt_input.toPlainText().strip()
            if not prompt:
                QMessageBox.warning(self, "Error", "Please enter a prompt")
                return

            size_text = self.img_size_combo.currentText()
            size_part = size_text.split(" ")[0]
            size_part = size_part.replace("(Landscape)", "").replace("(Portrait)", "").strip()

            style = self.img_style_combo.currentText().lower().replace(" ", "_")
            if style == "default":
                style = None
            elif style == "3d_render":
                style = "3d"

            strength = float(self.strength_slider.value() / 100)
            params = {
                "image_path": self.input_image_path,
                "prompt": prompt,
                "negative_prompt": self.img_negative_input.text(),
                "strength": strength,
                "style": style,
                "size": size_part,
            }
            self._active_btn = self.img_generate_btn
            self.worker = ImageGenerationWorker(self.api_client, params, mode="img2img")

        # Start generation (shared UI)
        self.txt_generate_btn.setEnabled(False)
        self.img_generate_btn.setEnabled(False)
        if hasattr(self, "_active_btn"):
            self._active_btn.setText("Generating...")
        self.progress.show()
        self._set_status_badge("queued")

        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.start()
    
    def on_generation_finished(self, data: dict):
        """Handle API response after creating a generation job (queue-aware)."""

        self.current_generation = data or {}
        gen_id = self.current_generation.get("id")
        status = (self.current_generation.get("status") or "").lower()

        # Queue-first: poll until completed/failed
        if not self.current_generation.get("result_url") and gen_id and status in {"queued", "pending", "processing"}:
            # keep UI responsive but prevent duplicate submissions
            self.txt_generate_btn.setEnabled(False)
            self.img_generate_btn.setEnabled(False)
            if hasattr(self, "_active_btn"):
                self._active_btn.setText("Queued…")
            self.progress.show()
            self._set_status_badge(status)
            self._start_polling(int(gen_id))
            self.refresh_history()
            return

        # If result is already available (sync provider), show it immediately
        if self.current_generation.get("result_url"):
            self.progress.hide()
            self._set_status_badge("completed")
            self.txt_generate_btn.setEnabled(True)
            self.img_generate_btn.setEnabled(True)
            self.txt_generate_btn.setText("Generate Image")
            self.img_generate_btn.setText("Generate (Image → Image)")
            self.download_btn.setEnabled(True)
            self.regenerate_btn.setEnabled(True)
            self._try_show_output_image(self.current_generation.get("result_url"))
            self.refresh_history()
            return

        # Unexpected response
        self._set_status_badge(status or "Idle")
    def on_generation_error(self, error: str):
        """Handle generation error"""
        self.txt_generate_btn.setEnabled(True)
        self.img_generate_btn.setEnabled(True)
        self.txt_generate_btn.setText("Generate Image")
        self.img_generate_btn.setText("Generate (Image → Image)")
        self.progress.hide()
        
        QMessageBox.critical(self, "Generation Failed", error)

    def on_upload_image(self):
        """Select input image for img2img."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if not file_path:
            return

        self.input_image_path = file_path
        self.upload_path_label.setText(Path(file_path).name)

        # Show input preview in the same preview area until we generate output
        try:
            img = QImage(file_path)
            if not img.isNull():
                pixmap = QPixmap.fromImage(img)
                scaled = pixmap.scaled(self.input_preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.input_preview_label.setPixmap(scaled)
        except Exception:
            pass
    
    def on_download(self):
        """Download generated image"""
        if not self.current_generation:
            return
        
        result_url = self.current_generation.get("result_url")
        if not result_url:
            return
        
        # Get file extension from URL
        ext = ".png"
        if "." in result_url:
            ext = "." + result_url.split(".")[-1].split("?")[0]
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            str(Path(self.config.download_path) / f"generated_image{ext}"),
            f"Images (*{ext});;All Files (*)",
        )
        
        if file_path:
            try:
                import httpx
                response = httpx.get(result_url)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                QMessageBox.information(self, "Success", "Image saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save image: {e}")