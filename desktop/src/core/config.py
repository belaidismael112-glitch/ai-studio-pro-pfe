"""Application configuration"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .secure_store import SecureTokenStore


@dataclass
class AppConfig:
    """Application configuration"""
    
    # API
    api_base_url: str = "http://localhost:8000/api/v1"
    
    # User tokens are stored in OS keychain (not on disk)
    access_token: str = ""  # populated from keyring
    refresh_token: str = ""  # populated from keyring
    user_email: str = ""
    user_credits: int = 0
    
    # Settings
    dark_mode: bool = True
    auto_save: bool = True
    default_image_width: int = 1024
    default_image_height: int = 1024
    default_video_duration: int = 4
    
    # Paths
    download_path: str = str(Path.home() / "AI Studio Pro" / "Downloads")
    
    def __post_init__(self):
        """Ensure download directory exists"""
        Path(self.download_path).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from file"""
        config_path = cls._get_config_path()
        
        cfg = cls()
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                # Do not load tokens from disk
                data.pop("access_token", None)
                data.pop("refresh_token", None)
                cfg = cls(**data)
            except Exception:
                pass

        # Load tokens from secure store
        cfg.access_token = SecureTokenStore.get_access_token()
        cfg.refresh_token = SecureTokenStore.get_refresh_token()
        return cfg
    
    def save(self):
        """Save configuration to file"""
        config_path = self._get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Persist non-sensitive settings only
        data = asdict(self)
        data.pop("access_token", None)
        data.pop("refresh_token", None)
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)

        # Store tokens securely
        SecureTokenStore.set_tokens(self.access_token, self.refresh_token)
    
    @staticmethod
    def _get_config_path() -> Path:
        """Get configuration file path"""
        if os.name == "nt":  # Windows
            config_dir = Path(os.environ.get("APPDATA", "")) / "AI Studio Pro"
        elif os.name == "posix":
            if os.uname().sysname == "Darwin":  # macOS
                config_dir = Path.home() / "Library" / "Application Support" / "AI Studio Pro"
            else:  # Linux
                config_dir = Path.home() / ".config" / "ai-studio-pro"
        else:
            config_dir = Path.home() / ".ai-studio-pro"
        
        return config_dir / "config.json"
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in"""
        return bool(self.access_token)
    
    def clear_auth(self):
        """Clear authentication data"""
        self.access_token = ""
        self.refresh_token = ""
        self.user_email = ""
        self.user_credits = 0
        SecureTokenStore.clear_tokens()
        self.save()
