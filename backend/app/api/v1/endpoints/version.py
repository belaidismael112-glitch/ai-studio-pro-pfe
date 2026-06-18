"""Version endpoints used by the desktop auto-updater."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/desktop")
async def desktop_version():
    """Return the latest desktop version and download URL."""
    # Backward-compatible response:
    # - desktop/src/core/updater.py consumes latest_version/download_url/release_notes.
    # - The PFE "final spec" expects version/changelog/download_url.
    release_notes = "Bug fixes and performance improvements."
    return {
        # New keys (spec)
        "version": settings.LATEST_DESKTOP_VERSION,
        "changelog": release_notes,
        "download_url": settings.DESKTOP_UPDATE_URL,

        # Legacy keys (desktop)
        "latest_version": settings.LATEST_DESKTOP_VERSION,
        "mandatory": False,
        "release_notes": release_notes,
    }
