# storage/__init__.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — STORAGE MODULE
# ============================================================================
# Core storage classes for Google Drive persistence
# ============================================================================

from storage.drive_storage import (
    GoogleDriveStorage,
    get_storage,
    DataType,
)

__all__ = [
    "GoogleDriveStorage",
    "get_storage",
    "DataType",
]
