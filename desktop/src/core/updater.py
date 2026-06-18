"""Desktop auto-updater (basic).

This implementation is intentionally minimal:
- It checks the backend endpoint /api/v1/version/desktop
- If a newer version exists and a download URL is provided, it downloads
  the installer and launches it.

For production, you'd typically add code-signing and a more robust updater.
"""

from __future__ import annotations

import os
import tempfile
import webbrowser
from dataclasses import dataclass
from typing import Optional

import httpx
from packaging.version import Version
from PySide6.QtWidgets import QMessageBox

from core.version import APP_VERSION


@dataclass
class UpdateInfo:
    latest_version: str
    download_url: Optional[str] = None
    mandatory: bool = False
    release_notes: str = ""


class Updater:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url.rstrip("/")

    def check(self) -> Optional[UpdateInfo]:
        url = f"{self.api_base_url}/version/desktop"
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            latest = data.get("latest_version")
            if not latest:
                return None

            if Version(latest) <= Version(APP_VERSION):
                return None

            return UpdateInfo(
                latest_version=latest,
                download_url=data.get("download_url"),
                mandatory=bool(data.get("mandatory", False)),
                release_notes=data.get("release_notes", ""),
            )
        except Exception:
            return None

    def prompt_and_update(self, parent, info: UpdateInfo) -> None:
        msg = (
            f"A new version is available: {info.latest_version}\n"
            f"You are running: {APP_VERSION}\n\n"
            f"Release notes:\n{info.release_notes or '-'}"
        )

        buttons = QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        if info.mandatory:
            buttons = QMessageBox.StandardButton.Ok

        choice = QMessageBox.information(
            parent,
            "Update available",
            msg,
            buttons,
        )

        if choice != QMessageBox.StandardButton.Ok:
            return

        if not info.download_url:
            QMessageBox.warning(parent, "Update", "No download URL configured.")
            return

        # Prefer opening URL in the browser (works everywhere)
        try:
            webbrowser.open(info.download_url)
            return
        except Exception:
            pass
