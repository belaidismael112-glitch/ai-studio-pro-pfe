"""Secure storage for secrets on Windows/macOS/Linux.

Uses the OS keychain through the `keyring` library.
"""

from __future__ import annotations

import keyring


class SecureTokenStore:
    SERVICE_NAME = "AI Studio Pro"

    @staticmethod
    def get_access_token() -> str:
        return keyring.get_password(SecureTokenStore.SERVICE_NAME, "access_token") or ""

    @staticmethod
    def get_refresh_token() -> str:
        return keyring.get_password(SecureTokenStore.SERVICE_NAME, "refresh_token") or ""

    @staticmethod
    def set_tokens(access_token: str, refresh_token: str) -> None:
        if access_token:
            keyring.set_password(SecureTokenStore.SERVICE_NAME, "access_token", access_token)
        if refresh_token:
            keyring.set_password(SecureTokenStore.SERVICE_NAME, "refresh_token", refresh_token)

    @staticmethod
    def clear_tokens() -> None:
        for key in ("access_token", "refresh_token"):
            try:
                keyring.delete_password(SecureTokenStore.SERVICE_NAME, key)
            except Exception:
                pass
